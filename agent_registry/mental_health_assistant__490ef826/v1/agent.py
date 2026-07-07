from dotenv import load_dotenv
load_dotenv()
import os
import logging
from typing import Annotated, List, TypedDict
import operator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from langchain_groq import ChatGroq

# Settings via environment (required by spec)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY= os.getenv("GROQ_API_KEY")

# Logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# LLM with tools will be bound later
#llm = ChatOpenRouter(model="openai/gpt-oss-120b:free", openrouter_api_key=OPENROUTER_API_KEY)
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0
)

# Search tool – capped to 3 results
search_tool = TavilySearch(max_results=3)

# Simple per‑thread memory for user notes (could be extended)
_sessions: dict = {}

def get_session(thread_id: str) -> dict:
    if thread_id not in _sessions:
        _sessions[thread_id] = {"notes": []}
    return _sessions[thread_id]

# ----- Tools ---------------------------------------------------------------
from langchain_core.tools import tool

@tool
def add_note(note: str) -> str:
    """Add a personal note for the current session. Useful for tracking feelings or events."""
    # thread_id will be supplied via the tool's context (see below)
    # The tool receives the current thread_id via the global config when called.
    # We'll fetch it from the environment variable set by the workflow runtime.
    # In this simple demo we rely on a global placeholder – in real usage the
    # thread_id is passed through the graph's configurable dict.
    import inspect
    frame = inspect.currentframe()
    while frame:
        if "thread_id" in frame.f_locals:
            thread_id = frame.f_locals["thread_id"]
            break
        frame = frame.f_back
    else:
        thread_id = "default"
    sess = get_session(thread_id)
    sess["notes"].append(note)
    return f"Note added to session {thread_id}."

@tool
def search_web(query: str) -> str:
    """Search the web for reliable information about mental health topics. Returns a short summary."""
    try:
        results = search_tool.run(query)
        # TavilySearch returns a list of dicts; we summarise titles + URLs
        summary = "\n".join([f"- {r.get('title', '')}: {r.get('url', '')}" for r in results])
        return summary or "No results found."
    except Exception as e:
        log.error(f"Tavily search failed: {e}")
        return f"Search error: {e}"

tools = [add_note, search_web]

# ----- State ---------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# ----- Nodes ---------------------------------------------------------------
def route_after_chatbot(state: dict) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

def chatbot_node(state: dict) -> dict:
    # Bind tools so the LLM can invoke them
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(state["messages"])
    log.info(f"LLM response content: {response.content!r}")
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    return {"messages": [response]}

# ----- Graph ---------------------------------------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))
workflow.set_entry_point("chatbot")
workflow.add_conditional_edges("chatbot", route_after_chatbot, {"tools": "tools", END: END})
workflow.add_edge("tools", "chatbot")
graph = workflow.compile(checkpointer=MemorySaver())

# ----- FastAPI -------------------------------------------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRequest(BaseModel):
    user_input: str
    thread_id: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("ui.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/run")
async def run_agent(body: AgentRequest):
    # Load prior messages from memory if any
    config = {"configurable": {"thread_id": body.thread_id}}
    # Retrieve stored state (if any) – MemorySaver handles this automatically
    # Ensure we start with a system prompt only once per thread
    existing_state = await graph.aget_state(config=config)
    messages: List[BaseMessage] = existing_state.values.get("messages", []) if existing_state.values else []
    if not messages:
        messages = [SystemMessage(content="You are a compassionate mental‑health assistant. Offer supportive, evidence‑based advice and use tools when appropriate.")]
    messages.append(HumanMessage(content=body.user_input))
    result = await graph.ainvoke({"messages": messages}, config=config)
    reply_msg = result["messages"][-1]
    return {"assistant_reply": reply_msg.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
