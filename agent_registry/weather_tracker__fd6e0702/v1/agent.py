"""How to test this agent:

Browser:
http://127.0.0.1:8000/

Terminal:
curl -X POST http://127.0.0.1:8000/run \
-H "Content-Type: application/json" \
-d '{"user_input": "What's the weather in London?", "thread_id": "test-1"}'
"""

from dotenv import load_dotenv
load_dotenv()

import os
import logging
from typing import Annotated, List, TypedDict
import operator
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# --- Settings Management ---
class Settings(BaseSettings):
    openrouter_api_key: str
    tavily_api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

# --- LLM and Tools ---
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")

# Tavily Search Tool
# max_results is capped to prevent runaway calls
search_tool = TavilySearch(max_results=3)

tools = [search_tool]
llm_with_tools = llm.bind_tools(tools)

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- Graph Nodes ---
def chatbot_node(state: AgentState) -> dict:
    log.info("Entering chatbot_node")
    response = llm_with_tools.invoke(state["messages"])
    log.info(f"LLM response: {response.content!r}")
    last_msg = state["messages"][-1]
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    return {"messages": [response]}

# --- Graph Routing ---
def route_after_chatbot(state: AgentState) -> str:
    log.info("Entering route_after_chatbot")
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        log.info("Routing to tools")
        return "tools"
    log.info("Routing to END")
    return END

# --- Graph Definition ---
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
app_graph = workflow.compile(checkpointer=memory)

# --- FastAPI Application ---
app = FastAPI(
    title="Weather Tracker Agent",
    description="An agent that can fetch weather information using Tavily Search.",
    version="1.0",
)

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

class AgentRequest(BaseModel):
    user_input: str
    thread_id: str = Field(default="thread-1", description="ID for the conversation thread.")

@app.post("/run")
async def run_agent(request: AgentRequest):
    log.info(f"Received request for thread_id: {request.thread_id}")
    config = {"configurable": {"thread_id": request.thread_id}}

    # Retrieve existing messages or initialize with a system message
    existing_state = app_graph.get_state(config)
    messages = existing_state.values.get("messages", []) if existing_state.values else []

    if not messages:
        messages.append(SystemMessage(content="You are a helpful AI assistant. Use the provided tools to answer questions, especially for current weather information. If you cannot find an answer, politely say so."))

    messages.append(HumanMessage(content=request.user_input))

    try:
        # Invoke the graph with the updated messages
        result = await app_graph.ainvoke({"messages": messages}, config=config)
        assistant_reply = result["messages"][-1].content
        log.info(f"Agent reply for thread {request.thread_id}: {assistant_reply!r}")
        return {"assistant_reply": assistant_reply}
    except Exception as e:
        log.error(f"Error running agent for thread {request.thread_id}: {e}")
        return {"assistant_reply": f"An error occurred: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
