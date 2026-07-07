from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.agents.graph import app_graph
from pydantic import BaseModel
import os

class ChatRequest(BaseModel):
    query: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "System operational"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    result = app_graph.invoke({"query": request.query})

    agent_spec = result["agent_spec"]
    agent_name = agent_spec.agent_name
    base = os.path.join("generated_agents", agent_name)

    # Debug — paste this output here
    print(f"[main] agent_name: {agent_name}")
    print(f"[main] base path: {base}")
    print(f"[main] agent.py exists: {os.path.exists(os.path.join(base, 'agent.py'))}")
    print(f"[main] ui.html exists:  {os.path.exists(os.path.join(base, 'ui.html'))}")
    print(f"[main] .env exists:     {os.path.exists(os.path.join(base, '.env'))}")
    print(f"[main] cwd: {os.getcwd()}")

    agent_py = read_file(os.path.join(base, "agent.py"))
    ui_html  = read_file(os.path.join(base, "ui.html"))
    env_file = read_file(os.path.join(base, ".env"))

    print(f"[main] agent.py length: {len(agent_py)}")
    print(f"[main] ui.html length:  {len(ui_html)}")

    return {
        "result": {
            "agent_py": agent_py,
            "env":      env_file,
            "ui_html":  ui_html,
        }
    }