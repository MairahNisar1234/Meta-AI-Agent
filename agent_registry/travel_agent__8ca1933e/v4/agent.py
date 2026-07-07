from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
from langchain_openrouter import ChatOpenRouter
from langchain_tavily import TavilySearch
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()
import logging
logging.basicConfig(level=logging.INFO, format="[%%(levelname)s] %%(message)s")
log = logging.getLogger(__name__)

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

llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
search_tool = TavilySearch(max_results=3)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("ui.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/run")
async def run_agent(body: AgentRequest):
    user_input = body.user_input
    response = await llm.ainvoke([user_input])
    log.info(f"tool_calls: {getattr(response, 'tool_calls', [])}")
    log.info(f"content: {response.content!r}")
    return {"assistant_reply": response.content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
