# generated_agents/mental_health_agent/agent.py
"""Mental Health Care Agent using LangGraph and FastAPI.

Features:
- Provides empathetic responses.
- Offers self‑care suggestions via a tool.
- Can perform a web search using Tavily for up‑to‑date resources.

Run with:
    python -m generated_agents.mental_health_agent.agent
"""

from __future__ import annotations

import os
import logging
from typing import Annotated, List, TypedDict
import operator

from dotenv import load_dotenv
load_dotenv()

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------- FastAPI setup ----------
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
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# ---------- LLM ----------
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")

# ---------- Tools ----------
search_tool = TavilySearch(max_results=3)

# Simple self‑care tip store (module level for mutation)
_self_care_tips: List[str] = []

@tool
def add_self_care_tip(tip: str) -> str:
    """Add a self‑care tip to the user's personal list.
    The tip is stored for the current session (identified by thread_id).
    """
    # store per‑thread using environment variable as a simple demo
    thread_id = os.getenv("CURRENT_THREAD_ID", "default")
    key = f"tips:{thread_id}"
    existing = os.getenv(key)
    # In a real deployment use a DB; here we just log the action.
    _self_care_tips.append(tip)
    return f"Tip added: \"{tip}\""

@tool
def list_self_care_tips() -> str:
    """Return the list of previously saved self‑care tips for this session.
    """
    if not _self_care_tips:
        return "No tips saved yet."
    formatted = "\n".join(f"- {t}" for t in _self_care_tips)
    return f"Your saved tips:\n{formatted}"

@tool
def web_search(query: str) -> str:
    """Search the web for mental‑health resources using Tavily.
    Returns up to 3 concise results.
    """
    try:
        results = search_tool.run(query)
        return results
    except Exception as e:
        return f"Search failed: {e}"

tools = [add_self_care_tip, list_self_care_tips, web_search]

# ---------- State definition ----------
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# ---------- Helper to initialise messages ----------
def get_initial_messages(thread_id: str) -> List[BaseMessage]:
    # Retrieve previous messages from checkpoint; if none, add system prompt.
    return [SystemMessage(content="You are a compassionate mental health assistant. Offer empathetic support, suggest self‑care tips, and only use web search when the user requests up‑to‑date information.")]

# ---------- Nodes ----------
def chatbot_node(state: AgentState):
    # Bind tools so the LLM can invoke them.
    response = llm.bind_tools(tools).invoke(state["messages"])
    log.info(f"LLM response content: {response.content!r}")
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
    # Store current thread id for tools that may need it (demo only)
    os.environ["CURRENT_THREAD_ID"] = request.thread_id
    # Build initial state with possible existing history
    existing = await app_graph.aget_state(config={"configurable": {"thread_id": request.thread_id}})
    messages = existing.values.get("messages", []) if existing.values else []
    if not messages:
        messages = get_initial_messages(request.thread_id)
    messages.append(HumanMessage(content=request.user_input))
    input_state: AgentState = {"messages": messages}
    result = await app_graph.ainvoke(input_state, config={"configurable": {"thread_id": request.thread_id}})
    final_msg = result["messages"][-1]
    # Ensure we return plain text for the UI
    return {"assistant_reply": final_msg.content}

# ---------- Run server ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
