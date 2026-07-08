from dotenv import load_dotenv
load_dotenv()

import os
import json
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from app.agents.graph import app_graph
from app.core.config import settings


class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default_session"


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_agent_result(result: dict) -> dict:
    """
    After the graph finishes, inspect the state to build a rich response.
    Returns a dict with:
      - result: human-readable completion message
      - agent_name: the canonical agent name (if code was generated)
      - files: list of generated file paths (relative, for download)
      - download_urls: {filename: /download/<agent>/<file>} map
    """
    spec = result.get("agent_spec")
    agent_name = getattr(spec, "agent_name", None) if spec else None

    # Check if files actually landed on disk
    generated_files: list[dict] = []
    if agent_name:
        agent_dir = Path(settings.generated_agents_dir) / agent_name
        for fname in ["agent.py", ".env", "ui.html"]:
            fpath = agent_dir / fname
            if fpath.exists():
                generated_files.append({
                    "name": fname,
                    "path": str(fpath),
                    "download_url": f"/download/{agent_name}/{fname}",
                    "size": fpath.stat().st_size,
                })

    # Build the human-readable message
    if generated_files:
        file_list = "\n".join(f"  • {f['name']}" for f in generated_files)
        message = (
            f"✅ **{agent_name}** has been generated successfully!\n\n"
            f"**Generated files ({len(generated_files)}):**\n{file_list}\n\n"
            f"**To run your agent:**\n"
            f"```bash\n"
            f"cd generated_agents/{agent_name}\n"
            f"pip install fastapi uvicorn langchain-openrouter langchain-tavily python-dotenv\n"
            f"# Add your API keys to .env\n"
            f"python agent.py\n"
            f"# Then open http://127.0.0.1:8000 in your browser\n"
            f"```"
        )
    else:
        # Fallback: grab last message content
        msgs = result.get("messages", [])
        last = msgs[-1] if msgs else None
        raw = last.content if last else ""
        # If it looks like JSON spec, give a friendlier message
        if raw.strip().startswith("{") and "agent_name" in raw:
            message = (
                "⚠️ Agent specification was parsed but code generation did not complete. "
                "Please try again with a more specific prompt."
            )
        else:
            message = raw or "Done."

    return {
        "result": message,
        "agent_name": agent_name,
        "files": generated_files,
        "task_type": getattr(spec, "task_type", "unknown") if spec else "unknown",
    }

# Routes

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "System operational"}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty.")
    try:
        initial_state = {
            "query": request.query,
            "messages": [],
            "agent_spec": None,
        }
        config = {"configurable": {"thread_id": request.thread_id}}
        result = app_graph.invoke(initial_state, config=config)
        return _build_agent_result(result)

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty.")

    async def event_generator():
        try:
            initial_state = {
                "query": request.query,
                "messages": [],
                "agent_spec": None,
            }
            config = {"configurable": {"thread_id": request.thread_id}}

            final_state: dict = {}

            async for event in app_graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                kind = event["event"]

                # Stream LLM tokens
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"].content
                    if chunk:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

                # Tool execution notifications
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    # Emit progress for file saves
                    tool_output = event["data"].get("output", "")
                    if isinstance(tool_output, str) and "Saved to" in tool_output:
                        # Extract which file was saved for progress feedback
                        saved_name = ""
                        for fname in ["agent.py", ".env", "ui.html"]:
                            if fname in tool_output:
                                saved_name = fname
                                break
                        yield f"data: {json.dumps({'type': 'file_saved', 'file': saved_name, 'tool': tool_name})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name})}\n\n"

                # Capture final state from the last node
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    final_state = event["data"].get("output", {})

            # ── Build the final rich response ────────────────────────────
            built = _build_agent_result(final_state)

            # Emit the agent_created event with all file info
            yield f"data: {json.dumps({'type': 'agent_created', **built})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            print(traceback.format_exc())
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/download/{agent_name}/{filename:path}")
async def download_file(agent_name: str, filename: str):
    """
    Serve a generated agent file for download.
    Supports: agent.py, .env, ui.html
    """
    # Sanitise — no path traversal
    safe_name = Path(agent_name).name
    safe_file = Path(filename).name

    allowed = {"agent.py", ".env", "ui.html"}
    if safe_file not in allowed:
        raise HTTPException(status_code=400, detail=f"File '{safe_file}' not available for download.")

    path = Path(settings.generated_agents_dir) / safe_name / safe_file
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {safe_file}")

    # For .env, use text/plain; others are fine as octet-stream
    media_type = "text/plain" if safe_file in (".env", "agent.py", "ui.html") else "application/octet-stream"
    return FileResponse(
        path=str(path),
        filename=safe_file,
        media_type=media_type,
    )


@app.get("/agents/list")
async def list_all_agents():
    """Return all active agents from the database with their file info."""
    from app.agents.persistence import list_agents
    agents = list_agents(status="active")
    result = []
    for agent in agents:
        agent_name = agent["canonical_name"]
        agent_dir = Path(settings.generated_agents_dir) / agent_name
        files = []
        for fname in ["agent.py", ".env", "ui.html"]:
            fpath = agent_dir / fname
            if fpath.exists():
                files.append({
                    "name": fname,
                    "download_url": f"/download/{agent_name}/{fname}",
                    "size": fpath.stat().st_size,
                })
        result.append({
            "id": agent["id"],
            "canonical_name": agent_name,
            "display_name": agent.get("display_name") or agent_name,
            "original_prompt": agent.get("original_prompt", ""),
            "category": agent.get("category", "none"),
            "current_version": agent.get("current_version", 1),
            "created_at": agent.get("created_at", ""),
            "metadata": agent.get("metadata", {}),
            "files": files,
            "has_files": len(files) > 0,
        })
    return {"agents": result, "total": len(result)}



async def list_agent_files(agent_name: str):
    """List available files for a generated agent."""
    safe_name = Path(agent_name).name
    agent_dir = Path(settings.generated_agents_dir) / safe_name

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{safe_name}' not found.")

    files = []
    for fname in ["agent.py", ".env", "ui.html"]:
        fpath = agent_dir / fname
        if fpath.exists():
            files.append({
                "name": fname,
                "download_url": f"/download/{safe_name}/{fname}",
                "size": fpath.stat().st_size,
            })

    return {"agent_name": safe_name, "files": files}
