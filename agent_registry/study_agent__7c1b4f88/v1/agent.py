from dotenv import load_dotenv
load_dotenv()
import os
import logging
from typing import List, Annotated
import operator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Settings & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM & Tools
# ---------------------------------------------------------------------------
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
search_tool = TavilySearch(max_results=3)  # key read from env automatically

# ---------------------------------------------------------------------------
# Simple in‑memory study notes store (per thread)
# ---------------------------------------------------------------------------
_sessions_notes: dict[str, dict[str, str]] = {}

def get_notes_store(thread_id: str) -> dict[str, str]:
    if thread_id not in sessions_notes:
        sessions_notes[thread_id] = {}
    return sessions_notes[thread_id]

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
from langchain_core.tools import tool

@tool
def add_note(title: str, content: str) -> str:
    """Add a study note under *title* with the given *content*.
    The note is stored per conversation thread.
    """
    # thread_id is injected via the LangGraph context variable
    from langgraph.graph import Message
    thread_id = Message.get_current_config().get("thread_id")
    notes = get_notes_store(thread_id)
    notes[title] = content
    return f"Note '{title}' added."

@tool
def get_note(title: str) -> str:
    """Retrieve the content of a previously saved note.
    Returns a helpful message if the note does not exist.
    """
    from langgraph.graph import Message
    thread_id = Message.get_current_config().get("thread_id")
    notes = get_notes_store(thread_id)
    if title in notes:
        return notes[title]
    return f"No note found with title '{title}'."

@tool
def web_search(query: str) -> str:
    """Search the web for *query* using Tavily and return a short summary.
    The tool returns the first result's snippet.
    """
    try:
        results = search_tool.run(query)
        if isinstance(results, list) and results:
            first = results[0]
            return first.get("snippet", "No snippet available.")
        return "No results found."
    except Exception as e:
        return f"Search failed: {str(e)}"

tools = [add_note, get_note, web_search]

# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------
from typing import TypedDict

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# ---------------------------------------------------------------------------
# FastAPI request model
# ---------------------------------------------------------------------------
class AgentRequest(BaseModel):
    user_input: str = Field(..., description="User message")
    thread_id: str = Field(..., description="Session identifier")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def route_after_chatbot(state):
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

async def chatbot_node(state):
    # Bind tools so the LLM can call them
    llm_with_tools = llm.bind_tools(tools)
    response = await llm_with_tools.ainvoke(state["messages"])
    log.info(f"LLM response: {response}")
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    return {"messages": [response]}

# ---------------------------------------------------------------------------
# Build workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))
workflow.set_entry_point("chatbot")
workflow.add_conditional_edges("chatbot", route_after_chatbot, {"tools": "tools", END: END})
workflow.add_edge("tools", "chatbot")

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.post("/run")
async def run_agent(request: AgentRequest):
    # Retrieve prior messages for this thread (if any)
    config = {"configurable": {"thread_id": request.thread_id}}
    # Get current state from memory (may be empty)
    prior = await app_graph.aget_state(config=config)
    msgs = prior.values.get("messages", []) if prior.values else []
    # Add system prompt once per thread
    if not msgs:
        msgs.append(SystemMessage(content="You are a helpful study assistant. Use the provided tools to search the web or manage your notes."))
    msgs.append(HumanMessage(content=request.user_input))
    # Invoke graph
    result = await app_graph.ainvoke({"messages": msgs}, config=config)
    # The last message is the assistant reply
    assistant_msg = result["messages"][-1]
    reply_text = assistant_msg.content if isinstance(assistant_msg, AIMessage) else str(assistant_msg)
    return {"assistant_reply": reply_text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
