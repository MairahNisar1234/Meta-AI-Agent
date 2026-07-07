from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openrouter import ChatOpenRouter
from langchain_community.tools import TavilySearchResults
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
import os
import logging
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthRequest(BaseModel):
    user_input: str
    thread_id: str

llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
search_tool = TavilySearch(max_results=3)
memory = MemorySaver()

workflow = StateGraph(
    llm=llm,
    tools=[search_tool],
    memory=memory
)

workflow.add_node("chatbot", llm)
workflow.add_node("tools", ToolNode([search_tool]))
workflow.add_edge("tools", "chatbot")
workflow.set_entry_point("chatbot")

logging.basicConfig(level=logging.INFO, format="[%%(levelname)s] %%(message)s")
log = logging.getLogger(__name__)

@app.post("/run")
async def run_agent(body: HealthRequest):
    user_input = body.user_input
    thread_id = body.thread_id
    state = workflow.get_state(thread_id)
    if not state:
        state = {"messages": []}
    state["messages"].append(user_input)
    result = workflow.ainvoke(state)
    log.info(f"tool_calls: {getattr(result, 'tool_calls', [])}")
    log.info(f"content: {result.content!r}")
    return {"assistant_reply": result.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
