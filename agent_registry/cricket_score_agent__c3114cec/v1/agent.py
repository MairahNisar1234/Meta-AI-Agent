"""How to test this agent:

Browser:
http://127.0.0.1:8000/

Terminal:
curl -X POST http://127.0.0.1:8000/run \
-H "Content-Type: application/json" \
-d '{"user_input": "What are the live cricket scores?", "thread_id": "test-1"}'
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import logging
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

from typing import Annotated, List, TypedDict
import operator

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_openrouter import ChatOpenRouter
from langchain_core.tools import tool

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

# --- FastAPI Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("ui.html", "r", encoding="utf-8") as f:
        return f.read()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# --- Environment and Settings ---
load_dotenv()

class Settings(BaseSettings):
    openrouter_api_key: str
    tavily_api_key: str # Not used directly, but kept for consistency with general rules
    cricbuzz_rapidapi_key: str = ""
    cricbuzz_rapidapi_host: str = "cricbuzz-cricket.p.rapidapi.com"
    cricket_live_url: str = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/live"
    cricket_recent_url: str = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/recent"
    cricket_upcoming_url: str = "https://cricbuzz-cricket.p.rapidapi.com/matches/v1/upcoming"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# --- LLM Setup ---
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free", openrouter_api_key=settings.openrouter_api_key)

# --- Cricbuzz helpers (VERIFIED TOOL CODE - DO NOT REWRITE) ──────────────────────────────────────────────────────────
CRICKET_LIVE_URL     = settings.cricket_live_url
CRICKET_RECENT_URL   = settings.cricket_recent_url
CRICKET_UPCOMING_URL = settings.cricket_upcoming_url
CRICBUZZ_RAPIDAPI_KEY  = settings.cricbuzz_rapidapi_key
CRICBUZZ_RAPIDAPI_HOST = settings.cricbuzz_rapidapi_host

def _call_cricbuzz(url: str) -> dict:
    if not CRICBUZZ_RAPIDAPI_KEY or CRICBUZZ_RAPIDAPI_KEY.startswith("YOUR_"):
        raise RuntimeError("CRICBUZZ_RAPIDAPI_KEY not configured or is a placeholder")
    headers = {
        "X-RapidAPI-Key": CRICBUZZ_RAPIDAPI_KEY,
        "X-RapidAPI-Host": CRICBUZZ_RAPIDAPI_HOST,
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _fallback_scrape() -> str:
    try:
        resp = requests.get("https://www.espncricinfo.com/live-cricket-score", timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        headlines = [h.get_text(strip=True) for h in soup.select("h1,h2,h3")][:5]
        return " | ".join(headlines) or "No headlines found"
    except Exception as e:
        return f"Fallback scrape error: {e}"

def _iter_matches(data: dict):
    for tm in data.get("typeMatches", []):
        for sm in tm.get("seriesMatches", []):
            for m in sm.get("seriesAdWrapper", {}).get("matches", []):
                yield m

@tool
def fetch_live_cricket(team: str = None) -> str:
    """Fetch matches currently in progress, optionally filtered by team name.
    Use this tool when the user asks for live, current, or real-time cricket scores.
    """
    try:
        data = _call_cricbuzz(CRICKET_LIVE_URL)
    except Exception as e:
        log.warning("Cricbuzz live failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if "progress" not in state and "innings break" not in state and "stumps" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "state": info.get("state"),
                        "status": info.get("status"), "start": start.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})

@tool
def fetch_recent_cricket(team: str = None, date: str = None) -> str:
    """Fetch finished matches, optionally filtered by team name and/or a YYYY-MM-DD date.
    Use this tool for queries about past matches, results 'on <date>', 'yesterday', or 'last match'.
    """
    try:
        data = _call_cricbuzz(CRICKET_RECENT_URL)
    except Exception as e:
        log.warning("Cricbuzz recent failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if "complete" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        if date and start.strftime("%Y-%m-%d") != date:
            continue
        end = datetime.fromtimestamp(int(info.get("endDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "result": info.get("status"),
                        "start": start.isoformat(), "end": end.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})

@tool
def fetch_upcoming_cricket(team: str = None) -> str:
    """Fetch scheduled/future matches, optionally filtered by team name.
    Use this tool for queries about upcoming matches, schedules, or future games.
    """
    try:
        data = _call_cricbuzz(CRICKET_UPCOMING_URL)
    except Exception as e:
        log.warning("Cricbuzz upcoming failed (%s). Falling back.", e)
        return f"[fallback] {_fallback_scrape()} | updated: {datetime.now(timezone.utc).isoformat()}"
    matches = []
    for m in _iter_matches(data):
        info = m.get("matchInfo", {})
        state = (info.get("state") or "").lower()
        if state and "preview" not in state and "toss" not in state and "scheduled" not in state:
            continue
        t1 = info.get("team1", {}).get("teamName", "")
        t2 = info.get("team2", {}).get("teamName", "")
        if team and team.lower() not in t1.lower() and team.lower() not in t2.lower():
            continue
        start = datetime.fromtimestamp(int(info.get("startDate", "0")) / 1000)
        matches.append({"team1": t1, "team2": t2, "start": start.isoformat()})
    return str({"matches": matches, "last_updated": datetime.now(timezone.utc).isoformat()})

# --- LangGraph Setup ---
tools = [fetch_live_cricket, fetch_recent_cricket, fetch_upcoming_cricket]
llm_with_tools = llm.bind_tools(tools)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

def chatbot_node(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    last_msg = state["messages"][-1]
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    log.info(f"content: {response.content!r}")
    return {"messages": [response]}

def route_after_chatbot(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

workflow = StateGraph(AgentState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("chatbot")
workflow.add_conditional_edges(
    "chatbot",
    route_after_chatbot,
    {"tools": "tools", END: END}
)
workflow.add_edge("tools", "chatbot")

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

# --- FastAPI Routes ---
class AgentRequest(BaseModel):
    user_input: str
    thread_id: str

@app.post("/run")
async def run_agent(body: AgentRequest):
    config = {"configurable": {"thread_id": body.thread_id}}
    
    # Retrieve existing messages for the thread
    existing_state = await graph.aget_state(config)
    messages = existing_state.values.get("messages", []) if existing_state.values else []

    # Add SystemMessage if it's a new thread
    if not messages:
        messages.append(SystemMessage(content="""You are a cricket data assistant with direct API access.

You have a real tool that fetches live cricket data from Cricbuzz (unofficial, free).
The API key is already configured in your environment.

RULES YOU MUST FOLLOW — NO EXCEPTIONS:
1. When the user asks for live, current, or real-time cricket data → ALWAYS call your tool immediately. Do NOT apologise. Do NOT say you cannot access live data.
2. NEVER say "I don't have access to real-time data" — you DO have access via your tools.
3. NEVER say "I cannot fetch live scores" — you CAN, using the tool provided.
4. NEVER apologise for not having data — just call the tool and return what it gives you.
5. If the tool returns an error → show the error message to the user, do not apologise.
6. Always call the tool FIRST, then interpret the result for the user.
"""))

    # Add the current user input
    messages.append(HumanMessage(content=body.user_input))

    # Invoke the graph
    result = await graph.ainvoke({"messages": messages}, config=config)
    
    assistant_reply = result["messages"][-1].content
    return {"assistant_reply": assistant_reply}

# --- Uvicorn Entry Point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
