# Development Standards for AI Agents

---

## 1. Imports and Dependencies

- **LLM Provider (MANDATORY):** Always use `ChatOpenRouter`. Never use `ChatOpenAI` or any direct OpenAI import. The `.env` must contain `OPENROUTER_API_KEY`, never `OPENAI_API_KEY`.
  ```python
  from langchain_openrouter import ChatOpenRouter
  llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
  ```
- **Core LangGraph:** Use `from langgraph.checkpoint.memory import MemorySaver`. Do NOT use `MemoryCheckpoint` (deprecated).
- **Tooling:** Use `from langgraph.prebuilt import ToolNode`. Do NOT import `tools` from `langgraph.prebuilt`.
- **Environment:** Always import and call `load_dotenv()` at the very top of the script.

---

## 2. Persistence and State Management

### Memory
```python
memory = MemorySaver()
```

### Config
Always pass thread_id inside configurable:
```python
# CORRECT
config = {"configurable": {"thread_id": "any_id_string"}}
result = await graph.ainvoke(state, config=config)

# INCORRECT — never do these
await graph.ainvoke(state, thread_id="123")
await graph.ainvoke(state, memory=memory)
```

### State Definition
Use `TypedDict`. All keys must be `Optional[T]` unless guaranteed to be set at start.
Never store `thread_id` in AgentState — it belongs only in the config dict.

---

## 3. Web Service & Execution

Always include at the bottom of every agent file:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

---

## 4. Code Generation & Formatting Standards

- Separate all code blocks from conversational text.
- Wrap every code block in triple backticks with a language identifier.
- Never place conversational text on the same line as a code block.
- When using `save_code_to_file`, the `code` argument must be a clean string using `\n` for newlines.

---

## 5. Data Fetching and Reliability

### Anti-Scraping Policy
Do NOT use raw `httpx` or `requests` for Yahoo Finance, Google, or similar providers — they block basic Python headers.

### Approved Libraries
- **Finance:** `yfinance`
- **Web Search:** Use `TavilySearchResults` from `langchain_community.tools` (not the deprecated `.tavily_search` submodule)
- **General APIs:** Include a browser-like User-Agent header in `httpx` requests.

### Correct Tavily Usage
```python
# CORRECT — key is read from TAVILY_API_KEY env var automatically
from langchain_community.tools import TavilySearchResults
search_tool = TavilySearchResults(max_results=3)

# BANNED — deprecated submodule
from langchain_community.tools.tavily_search import TavilySearchResults  # ← deprecated

# BANNED — package does not exist
from langchain_tavily import TavilySearch  # ← ModuleNotFoundError

# BANNED — never pass key in constructor
TavilySearch(tavily_api_key=...)  # ← wrong
```

### Error Handling
Every tool function must have a `try/except` block catching `HTTPStatusError` or `ValueError` and returning a descriptive string to the LLM.

---

## 6. FastAPI & API Standards

- Always use Pydantic models for request bodies.
- Never use `request: Request` and `await request.json()`.

```python
from pydantic import BaseModel

class AgentRequest(BaseModel):
    user_input: str
    thread_id: str

@app.post("/run")
async def run_agent(body: AgentRequest):
    user_input = body.user_input
```

---

## 7. Agent Logic and Routing

### Determinism
For simple sequential tasks use hardcoded edges:
```
START -> node_a -> node_b -> END
```

### Conditional Logic
For multi-tool decisions use `add_conditional_edges` with a custom routing function based on the LLM's last message.

---

## 8. Memory & Checkpointing Standards

```python
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)
```

- Do NOT import `CheckpointID` from `langgraph.checkpoint.base` — it does not exist.
- Do NOT pass `memory=` to `ainvoke()` — memory is attached at compile time only.

---

## 9. Testing Instructions

Every generated `agent.py` must include a comment header explaining how to test it.

### Browser
```
http://127.0.0.1:8000/docs
```

### Terminal
```bash
curl -X POST http://127.0.0.1:8000/run \
-H "Content-Type: application/json" \
-d '{"user_input": "hello", "thread_id": "test-1"}'
```

---

## 10. UI Generation Standards

Every generated agent MUST be accompanied by a `ui.html` file in the same directory.

### Requirements
- Single self-contained HTML file — HTML + CSS + JS in one file, no frameworks, no CDN.
- Input fields must **exactly match** the Pydantic request model field names in `agent.py`.
- The UI must be **fully wired** to the backend — it must call the agent and display its real response.
- Must call POST `http://127.0.0.1:8000/run` via `fetch()` with `Content-Type: application/json`.
- The JSON body must use the **exact same field names** as the Pydantic model (e.g. `user_input`, `thread_id`).
- Always include a `thread_id` field (default `"thread-1"`) in the request body.
- Must show a loading spinner while waiting and disable the Submit button during the request.
- Must display the main reply field from the JSON response in a readable block.
- Must show a red error message if the fetch fails or the server returns a non-200 status.
- Save using `save_code_to_file` to `generated_agents/<agent_name>/ui.html`.

### Required fetch pattern
```javascript
const res = await fetch("http://127.0.0.1:8000/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_input: inputValue, thread_id: "thread-1" })
});
if (!res.ok) throw new Error(`Server error: ${res.status}`);
const data = await res.json();
resultDiv.textContent = data.assistant_reply ?? JSON.stringify(data, null, 2);
```

---

## 11. Graph Compilation Rules

- ALWAYS compile the graph at module level BEFORE defining FastAPI routes:
  ```python
  graph = workflow.compile(checkpointer=memory)
  ```
- NEVER call `.ainvoke()` on a `StateGraph` (workflow) directly — only on the compiled graph.
- NEVER pass `memory=` as an argument to `ainvoke()`.
- NEVER store `thread_id` in AgentState.

---

## 12. Settings & Configuration

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    openrouter_api_key: str
    tavily_api_key: str
    generated_agents_dir: str = "generated_agents"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

- Never use `class Config` — that is the old Pydantic v1 pattern.
- Never use `os.getenv()` directly — always go through the Settings object.
- Only declare API keys that the agent actually uses — extra required fields crash on startup.

---

## 13. Mandatory Import Cheatsheet (STRICT — NO EXCEPTIONS)

If an import path is not listed here, do NOT guess. Only use paths from this list.

### Messages
```python
# CORRECT
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

# BANNED — will crash
from langchain.schema import HumanMessage
from langchain.schema import AIMessage
from langchain.schema import SystemMessage
```

### Chat Models
```python
# CORRECT — always use ChatOpenRouter
from langchain_openrouter import ChatOpenRouter
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")

# BANNED — never use ChatOpenAI or any openai direct import
from langchain_openai import ChatOpenAI       # BANNED — use ChatOpenRouter
from langchain.chat_models import ChatOpenAI  # BANNED — will crash
```

### Tools
```python
# CORRECT
from langchain_community.tools.tavily_search import TavilySearchResults

# BANNED — will crash
from langchain.tools import TavilySearchResults
```

### LangGraph
```python
# CORRECT
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# BANNED — these modules do not exist
from langgraph.agent import ...
from langgraph.agents import ...
from langgraph.prebuilt import tools
from langgraph.checkpoint.base import CheckpointID
```

### Pydantic
```python
# CORRECT
from pydantic_settings import BaseSettings, SettingsConfigDict

# BANNED — old Pydantic v1 style
from pydantic import BaseSettings
```

---

## 14. Banned Imports — These Do Not Exist

| Banned import | Reason |
|---|---|
| `from langchain_openai import ChatOpenAI` | Use ChatOpenRouter — never use ChatOpenAI directly |
| `from langchain_openai import OpenAI` | Use ChatOpenRouter instead |
| `from langgraph.agent import ...` | Module does not exist — use StateGraph |
| `from langgraph.agents import ...` | Module does not exist — use StateGraph |
| `from langgraph.prebuilt import tools` | Use ToolNode instead |
| `from langgraph.prebuilt import AgentExecutor` | Does not exist — use StateGraph |
| `from langgraph.checkpoint.base import CheckpointID` | Removed |
| `from langchain.schema import ...` | Moved to langchain_core.messages |
| `from langchain.chat_models import ...` | Moved to langchain_openai |
| `from langchain.llms import ...` | Moved to langchain_openai |
| `from langchain.tools import ...` | Moved to langchain_community.tools |
| `from langchain.agents import AgentExecutor` | Use LangGraph StateGraph instead |
| `from langchain.memory import ...` | Use langgraph.checkpoint.memory |
| `from pydantic import BaseSettings` | Moved to pydantic_settings |

---

## 15. Common Node & Graph Mistakes

### State mutation
```python
# WRONG — mutating state corrupts LangGraph's state tracking
state["messages"].append(new_msg)

# CORRECT — always return new state
return {"messages": state["messages"] + [new_msg]}
```

### Binding tools to LLM
```python
# WRONG — LLM does not know tools exist
response = await llm.ainvoke(state["messages"])

# CORRECT — bind tools so LLM can call them
response = await llm.bind_tools([search_tool]).ainvoke(state["messages"])
```

### Tool node routing
```python
# WRONG — tool result never reaches the LLM
workflow.add_edge("tools", END)

# CORRECT — loop back so LLM processes the tool result
workflow.add_edge("tools", "chatbot")
```

### System prompt deduplication
Never add a SystemMessage on every API call. MemorySaver restores previous messages,
so repeating the system prompt creates duplicates on every turn. Only add it when
the thread has no existing messages:
```python
existing = graph.get_state(config)
messages = existing.values.get("messages", []) if existing.values else []
if not messages:
    messages = [SystemMessage(content="You are a helpful agent.")]
messages.append(HumanMessage(content=request.user_input))
```

### Model name for ChatOpenRouter
```python
# WRONG — "openrouter/" prefix does not exist
llm = ChatOpenRouter(model_name="openrouter/gpt-oss-120b:free")

# CORRECT
llm = ChatOpenRouter(model_name="openai/gpt-oss-120b:free")


### Web Search Tool (MANDATORY UPDATE)
- DO NOT use `langchain_community.tools.tavily_search`.
- ALWAYS use the modern package:
  ```python
  from langchain_tavily import TavilySearch
  # Initialization:
  search_tool = TavilySearch(tavily_api_key=settings.tavily_api_key)
```