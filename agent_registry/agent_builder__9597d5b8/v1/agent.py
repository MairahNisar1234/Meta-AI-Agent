"""Agent that uses LangGraph and Tavily Search."""

from dotenv import load_dotenv
load_dotenv()
import os
import logging
from typing import Annotated, List, TypedDict, Optional
import operator
from functools import lru_cache

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_openrouter import ChatOpenRouter
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

# --- Tools ---
search_tool = TavilySearch(tavily_api_key=settings.tavily_api_key, max_results=3)
tools = [search_tool]

# --- LLM Setup ---
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
llm_with_tools = llm.bind_tools(tools)

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- Graph Nodes ---
def chatbot_node(state: AgentState) -> dict:
    """Invokes the LLM with the current messages and returns the response."""
    log.info("Entering chatbot_node")
    response = llm_with_tools.invoke(state["messages"])
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    log.info(f"content: {response.content!r}")
    return {"messages": [response]}

def route_after_chatbot(state: AgentState) -> str:
    """Routes to tools if tool_calls are present, otherwise ends the conversation."""
    log.info("Entering route_after_chatbot")
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        log.info("Routing to tools")
        return "tools"
    log.info("Routing to END")
    return END

# --- LangGraph Setup ---
workflow = StateGraph(AgentState)

workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("chatbot")
workflow.add_conditional_edges(
    "chatbot",
    route_after_chatbot,
    {"tools": "tools", END: END},
)
workflow.add_edge("tools", "chatbot")

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)

# --- FastAPI Setup ---
app = FastAPI(
    title="Agent Builder",
    description="A simple LangGraph agent with Tavily Search.",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AgentRequest(BaseModel):
    user_input: str
    thread_id: str = Field(default="thread-1", description="Identifier for the conversation thread.")

class AgentResponse(BaseModel):
    assistant_reply: str
    thread_id: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the HTML user interface."""
    with open("generated_agents/agent_builder/ui.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """Run the agent with user input and return the assistant's reply."""
    log.info(f"Received request for thread_id: {request.thread_id}")
    config = {"configurable": {"thread_id": request.thread_id}}

    # Retrieve existing messages or initialize with a system message if new thread
    existing_state = app_graph.get_state(config)
    messages = existing_state.values.get("messages", []) if existing_state.values else []

    if not messages:
        messages.append(SystemMessage(content="You are a helpful AI assistant. Use the search tool to answer questions about current events or facts."))

    messages.append(HumanMessage(content=request.user_input))

    try:
        # Invoke the graph with the updated messages
        result = await app_graph.ainvoke({"messages": messages}, config=config)
        assistant_reply = result["messages"][-1].content
        log.info(f"Agent reply for thread {request.thread_id}: {assistant_reply!r}")
        return AgentResponse(assistant_reply=assistant_reply, thread_id=request.thread_id)
    except Exception as e:
        log.error(f"Error running agent for thread {request.thread_id}: {e}")
        return AgentResponse(assistant_reply=f"An error occurred: {e}", thread_id=request.thread_id)


if __name__ == "__main__":
    import uvicorn
    log.info("Starting FastAPI application...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
