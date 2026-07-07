# generated_agents/mental_health_agent/agent.py
"""Mental Health Care Agent using LangGraph and FastAPI.

Features:
- Provides empathetic responses.
- Offers self‑care suggestions via tools.
- Can perform a web search using Tavily for up‑to‑date resources.

Run with:
    python -m generated_agents.mental_health_agent.agent
"""

from __future__ import annotations

import os
import logging
import operator
from typing import Annotated, List, TypedDict

from dotenv import load_dotenv
load_dotenv()

# ---------- FastAPI setup (non‑negotiable) ----------
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

# ---------- Pydantic request model ----------
from pydantic import BaseModel

class AgentRequest(BaseModel):
    user_input: str
    thread_id: str

# ---------- LangChain / LangGraph imports ----------
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage,
    BaseMessage,
)
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------- LLM ----------
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")

# ---------- Tools ----------
search_tool = TavilySearch(max_results=3)

# Session‑scoped storage for self‑care tips
_sessions_tips: dict[str, List[str]] = {}

def _get_tip_store(thread_id: str) -> List[str]:
    return _sessions_tips.setdefault(thread_id, [])

@tool
def add_self_care_tip(tip: str) -> str:
    """Add a self‑care tip for the current session.
    The tip is stored in memory keyed by the provided thread_id.
    """
    thread_id = os.getenv("CURRENT_THREAD_ID", "default")
    store = _get_tip_store(thread_id)
    store.append(tip)
    return f"✅ Tip saved: \"{tip}\""

@tool
def list_self_care_tips() -> str:
    """Return all saved self‑care tips for the current session."""
    thread_id = os.getenv("CURRENT_THREAD_ID", "default")
    store = _get_tip_store(thread_id)
    if not store:
        return "You have not saved any tips yet."
    formatted = "\n".join(f"- {t}" for t in store)
    return f"Your saved tips:\n{formatted}"

@tool
def web_search(query: str) -> str:
    """Search the web for mental‑health resources using Tavily.
    Returns up to 3 concise results.
    """
    try:
        return search_tool.run(query)
    except Exception as e:
        return f"Search failed: {e}"

tools = [add_self_care_tip, list_self_care_tips, web_search]

# ---------- State definition ----------
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# ---------- Helper for initial system message ----------
def get_initial_messages() -> List[BaseMessage]:
    return [
        SystemMessage(
            content=(
                "You are a compassionate mental‑health assistant. "
                "Offer empathetic support, suggest self‑care tips, "
                "and only use web search when the user explicitly asks for up‑to‑date information."
            )
        )
    ]

# ---------- Nodes ----------
llm_with_tools = llm.bind_tools(tools)

def chatbot_node(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])  # returns AIMessage (may contain tool calls)
    log.info(f"LLM response: {response.content!r}")
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    return {"messages": [response]}

def route_after_chatbot(state: AgentState):
    last_msg = state["messages"][-1]
    return "tools" if getattr(last_msg, "tool_calls", None) else END

# ---------- Graph construction ----------
workflow = StateGraph(AgentState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_edge("tools", "chatbot")
workflow.add_conditional_edges(
    "chatbot",
    route_after_chatbot,
    {"tools": "tools", END: END},
)
workflow.set_entry_point("chatbot")

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)

# ---------- FastAPI endpoint ----------
@app.post("/run")
async def run_agent(request: AgentRequest):
    # expose thread_id to tools via env var (simple demo isolation)
    os.environ["CURRENT_THREAD_ID"] = request.thread_id

    # retrieve existing state from checkpoint
    existing = await app_graph.aget_state(config={"configurable": {"thread_id": request.thread_id}})
    messages = existing.values.get("messages", []) if existing.values else []
    if not messages:
        messages = get_initial_messages()
    messages.append(HumanMessage(content=request.user_input))

    input_state: AgentState = {"messages": messages}
    result = await app_graph.ainvoke(input_state, config={"configurable": {"thread_id": request.thread_id}})
    final_msg = result["messages"][-1]
    return {"assistant_reply": final_msg.content}

# ---------- Run server ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
