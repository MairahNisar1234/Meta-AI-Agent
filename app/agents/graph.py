from dotenv import load_dotenv
from typing import TypedDict, Optional, Annotated
import operator
import os
import subprocess
from app.core.config import settings
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openrouter import ChatOpenRouter
from langchain_tavily import TavilySearch
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from app.agents.schema import AgentSpec
from app.agents.coder_tools import save_code_to_file, set_canonical_agent_name, reset_canonical_agent_name
from app.core.parser import parse_query_to_spec
from app.agents.realtime_detector import realtime_detector_node
from app.agents.code_fixes import fix_code_in_tool_calls, validate_generated_code
from app.agents.persistence import init_db
from app.agents.persistence import save_agent
from app.agents.persistence import save_new_version, get_active_code_path, get_agent_by_canonical_name
#from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI



load_dotenv()
init_db() 

# ---------------------------------------------------------------------------
# Dev Standards Loader
# ---------------------------------------------------------------------------

def load_dev_standards() -> str:
    from pathlib import Path
    current = Path(__file__).resolve()
    for parent in [current.parent] + list(current.parents):
        candidate = parent / "dev_standards.md"
        if candidate.exists():
            print(f"[INFO] Loaded standards from: {candidate}")
            return candidate.read_text(encoding="utf-8")
    print("[WARNING] dev_standards.md not found")
    return ""
def load_ui_standards() -> str:
    from pathlib import Path
    current = Path(__file__).resolve()
    for parent in [current.parent] + list(current.parents):
        candidate = parent / "ui_standards.md"
        if candidate.exists():
            print(f"[INFO] Loaded UI standards from: {candidate}")
            return candidate.read_text(encoding="utf-8")
    print("[WARNING] ui_standards.md not found")
    return ""

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

search_tool = TavilySearch(max_results=2)
coder_tools = [save_code_to_file]
research_tools = [search_tool]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    query: str
    messages: Annotated[list[BaseMessage], operator.add]
    agent_spec: Optional[AgentSpec]
    next_agent: str
    realtime_config:  Optional[dict]
    agent_id: Optional[str]


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

#llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.gemini_api_key,
    temperature=0,
)
# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def parser_node(state: AgentState) -> dict:
    spec = parse_query_to_spec(state["query"])
    
    if spec is None:
        raise ValueError(
            f"[parser] parse_query_to_spec returned None for query: '{state['query']}'\n"
            "Check parser.py — the LLM response likely failed to parse into AgentSpec."
        )
    
    print(
        f"[parser] task_type={spec.task_type} | "
        f"requires_web={spec.requires_web_search} | "
        f"tools={spec.tools_needed}"
    )
    return {
        "agent_spec": spec,
        "messages": [HumanMessage(content=state["query"])],
    }

def supervisor_node(state: AgentState) -> dict:
    spec = state["agent_spec"]
    next_agent = "coder" if spec and spec.task_type == "code_gen" else "researcher"
    print(f"[supervisor] routing to → {next_agent}")
    return {"next_agent": next_agent}


def research_node(state: AgentState) -> dict:
    print(f"[researcher] messages in state: {len(state['messages'])}")
    system = SystemMessage(content=(
        "You are a Researcher. "
        f"Use the {search_tool.name} tool to find current facts. "
        "Always call the tool before answering — never rely on memory for recent events."
    ))
    response = llm.bind_tools(research_tools).invoke([system] + state["messages"])
    print(f"[researcher] tool_calls: {response.tool_calls}")
    return {"messages": [response]}


def coder_node(state: AgentState) -> dict:
    """
    Generates agent.py, .env, and ui.html.
    Retries up to 3 times if the model returns fewer than 3 tool calls.
    """
    spec = state.get("agent_spec")

    # Reset first — prevents stale name from a previous request leaking in.
    # Then lock the canonical name before the LLM is ever invoked.
    reset_canonical_agent_name()
    agent_name = None
    if hasattr(spec, "agent_name") and spec.agent_name:
        agent_name = spec.agent_name
    if agent_name:
        set_canonical_agent_name(agent_name)
    else:
        agent_name = "<agent_name>"

    # ── DB lookup — load previous version as reference if it exists ──────────
    prior_code_context = ""
    try:
        existing = get_agent_by_canonical_name(agent_name)
        if existing:
            prev_path = get_active_code_path(existing["id"])
            if prev_path:
                agent_py_path = os.path.join(prev_path, "agent.py")
                if os.path.exists(agent_py_path):
                    with open(agent_py_path, encoding="utf-8") as f:
                        prev_code = f.read()
                    prior_code_context = f"""
## 📂 PREVIOUS VERSION OF THIS AGENT (from database — v{existing['current_version']})

This agent already exists in the database. The user is regenerating or improving it.
Here is the last working version of agent.py for reference:

```python
{prev_code[:6000]}{'...[truncated]' if len(prev_code) > 6000 else ''}
```

Use this as a BASE. Keep what works, improve what the user asked to change.
Do NOT start from scratch — build on the existing code above.
"""
                    print(f"[coder] Loaded prior v{existing['current_version']} from DB for: {agent_name}")
    except Exception as e:
        print(f"[coder] DB lookup failed (non-fatal): {e}")
        prior_code_context = ""

    dev_standards = load_dev_standards()
    ui_standards = load_ui_standards()

    # ── Build realtime block from state (set by realtime_detector_node) ──────
    realtime_config = state.get("realtime_config")
    if realtime_config:
        rc = realtime_config
        key_line = (
            f"- Key env var  : {rc['key_env_var']} (already written to .env as placeholder)\n"
            f"  Signup (free): {rc['signup_url']}\n"
            f"  Free tier    : {rc['free_tier']}"
            if rc.get("requires_key") else
            "- No API key required — free, open endpoint"
        )
        realtime_block = f"""
## ⚡ REAL-TIME DATA REQUIREMENTS — READ CAREFULLY, IMPLEMENT FULLY

This agent needs live data. You MUST write real HTTP calls — NO simulated/placeholder data.

Category     : {rc['category']}
API to use   : {rc['api_name']}
Base URL     : {rc['base_url']}
Live endpoint: {rc['live_url']}
Fallback URL : {rc['fallback_url']} ({rc['fallback_type']})
{key_line}

CODING INSTRUCTIONS (follow exactly):
{rc['code_hint']}

MANDATORY IMPLEMENTATION RULES:
1. Import and use requests (or httpx) to make REAL HTTP calls to the live endpoint above.
2. NEVER simulate data, never use match_store/fake dicts as primary data source.
3. Read ALL API keys with os.getenv("VAR_NAME") — they are in the .env already.
4. If the primary API key is missing or the call fails, use the fallback URL.
5. ALWAYS include a "last_updated" timestamp (datetime.utcnow().isoformat()) in every live response.
6. The @tool function that fetches live data MUST call the real endpoint — not return hardcoded strings.

{f'''## ✅ VERIFIED TOOL CODE — COPY THIS EXACTLY, DO NOT REWRITE IT

The following tool implementation is pre-validated and known to work correctly
with the {rc["api_name"]} API response format.
COPY IT VERBATIM into agent.py — do NOT invent your own version.
The LLM-invented alternatives have wrong state filters and return empty results.

{rc["tool_template"]}
''' if rc.get("tool_template") else f'''EXAMPLE PATTERN (adapt to this agent's API):
@tool
def get_live_data(query: str) -> str:
    \\"\\"\\"Fetch live data from {rc['api_name']}.\\"\\"\\"
    import requests
    from datetime import datetime
    key = os.getenv("{rc.get('key_env_var') or 'API_KEY'}", "")
    if not key or key.startswith("YOUR_"):
        resp = requests.get("{rc['fallback_url']}", timeout=8)
        return f"[fallback] {{resp.text[:500]}} | updated: {{datetime.utcnow().isoformat()}}"
    headers = {{"X-RapidAPI-Key": key, "X-RapidAPI-Host": os.getenv("{rc.get('host_env_var') or ''}", "")}}
    resp = requests.get("{rc['live_url']}", headers=headers, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    return f"{{data}} | updated: {{datetime.utcnow().isoformat()}}"
'''}

## ⚡ SYSTEM PROMPT FOR THE GENERATED AGENT — USE THIS EXACT TEXT

The SystemMessage you write inside agent.py MUST contain this exact instruction block
(replace placeholders with the actual tool names and API name):

SystemMessage(content=\"\"\"You are a {rc['category']} data assistant with direct API access.

You have a real tool that fetches live {rc['category']} data from {rc['api_name']}.
The API key is already configured in your environment.

RULES YOU MUST FOLLOW — NO EXCEPTIONS:
1. When the user asks for live, current, or real-time {rc['category']} data → ALWAYS call your tool immediately. Do NOT apologise. Do NOT say you cannot access live data.
2. NEVER say "I don't have access to real-time data" — you DO have access via your tools.
3. NEVER say "I cannot fetch live scores" — you CAN, using the tool provided.
4. NEVER apologise for not having data — just call the tool and return what it gives you.
5. If the tool returns an error → show the error message to the user, do not apologise.
6. Always call the tool FIRST, then interpret the result for the user.
\"\"\")

This system prompt is NON-NEGOTIABLE. The LLM in the generated agent will refuse to call
tools if the system prompt does not explicitly forbid apologising and mandate tool use.
"""
    else:
        realtime_block = ""

    system = SystemMessage(content=f"""
You are a senior Python engineer building LangGraph + FastAPI apps.
{prior_code_context}
## ⚠️ NON-NEGOTIABLE REQUIREMENT

You MUST call save_code_to_file **3 times** in this response — one call per file.
If you call it fewer than 3 times, the task is INCOMPLETE and FAILED.

REQUIRED FILES — all 3, use EXACTLY this folder name: {agent_name}
1. save_code_to_file(filename="generated_agents/{agent_name}/agent.py", code="...")
2. save_code_to_file(filename="generated_agents/{agent_name}/.env",      code="...")
3. save_code_to_file(filename="generated_agents/{agent_name}/ui.html",   code="...")

⚠️ The folder name is fixed: "{agent_name}" — do NOT invent a different name.

---

# HARD RULES

## LLM
from langchain_openrouter import ChatOpenRouter
llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
NEVER use: ChatOpenAI, OpenAI, OPENAI_API_KEY, gpt-3.5-turbo, gpt-4, TavilySearchResults, langchain_tavily.TavilySearchResults

## PYDANTIC — ALWAYS IMPORT FROM pydantic DIRECTLY
from pydantic import BaseModel, Field
# NEVER: from langchain_core.pydantic_v1 import BaseModel  — removed, ModuleNotFoundError
# NEVER: from langchain.pydantic_v1 import BaseModel       — removed, ModuleNotFoundError
# langchain_core.pydantic_v1 was a compatibility shim that no longer exists.
# Always import straight from pydantic:

## agent.py MUST contain
from dotenv import load_dotenv
load_dotenv()
import os
...
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

## API KEYS
os.getenv("OPENROUTER_API_KEY")
os.getenv("TAVILY_API_KEY")

## TAVILY — CORRECT USAGE ONLY
from langchain_tavily import TavilySearch
search_tool = TavilySearch(max_results=3)
# Key is read from TAVILY_API_KEY env var automatically
# NEVER pass tavily_api_key= or any extra args — they cause duplicate keyword errors
# NEVER: TavilySearchResults (deprecated class name)
# NEVER: TavilySearch(max_results=3, max_results=3) — no duplicate kwargs ever

## TOOL ROUTING — THE ONLY CORRECT PATTERN
def route_after_chatbot(state):
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END
# NEVER iterate all messages looking for tool_calls
# NEVER: lambda state: "tools" if any(isinstance(m, dict) and m.get("tool_calls") ...)
# NEVER: check isinstance(m, dict) — LangGraph messages are objects, not dicts

## CHATBOT NODE — RETURN THE FULL AIMessage, NEVER REBUILD IT
def chatbot_node(state):
    response = llm_with_tools.invoke(state["messages"])
    return {{"messages": [response]}}
# NEVER: return {{"messages": [AIMessage(content=response.content)]}}
# Rebuilding AIMessage strips tool_calls — tools will silently fail

## TOOL NODE — USE ToolNode, NEVER WRITE YOUR OWN
workflow.add_node("tools", ToolNode(tools))
workflow.add_edge("tools", "chatbot")
# NEVER: workflow.add_edge("tools", END)  — LLM never sees tool results

## TOOL DEFINITIONS — @tool DECORATOR IS MANDATORY
# ToolNode calls tool_.name on every tool. Plain Python functions do NOT have a .name
# attribute and will crash at runtime with an AttributeError.
# EVERY tool passed to ToolNode MUST be decorated with @tool.
#
# WRONG — crashes ToolNode:
# def add_item(name: str, qty: int) -> str: ...
# tools = [add_item]
# ToolNode(tools)  <- AttributeError: function has no .name
#
# CORRECT:
# from langchain_core.tools import tool
#
# @tool
# def add_item(name: str, qty: int) -> str:
#     "Add an item to the inventory."
#     ...
#
# tools = [add_item]
# ToolNode(tools)  <- works correctly
#
# ALSO WRONG — passing a dict of functions:
# tools = {{"add_item": add_item, "search_item": search_item}}
# ToolNode(tools)  <- ToolNode expects a LIST, not a dict
#
# ALWAYS pass tools as a list: tools = [add_item, search_item]
## IMPORTS MUST MATCH USAGE — NO PHANTOM CLASS NAMES
# If you write: from langchain_tavily import TavilySearch
# Then you MUST use: search_tool = TavilySearch(max_results=3)
# NEVER use TavilySearchResults after importing TavilySearch — it will NameError immediately.
# Rule: every class you instantiate must appear in an import at the top of the file.

## TOOLS MUST ACTUALLY MUTATE STATE — NO FAKE STRING-RETURN TOOLS
# A tool that only returns a formatted string does NOTHING.
# The inventory/database/state is NEVER updated by returning "ADD_ITEM::laptop::SKU123::10".
#
# WRONG — tool does nothing:
# @tool
# def add_item(name: str, sku: str, quantity: int) -> str:
#     return f"ADD_ITEM::{{name}}::{{sku}}::{{quantity}}"   <- this changes nothing
#
# CORRECT — tool actually mutates shared state:
# inventory_db: dict = {{}}   # module-level store
#
# @tool
# def add_item(name: str, sku: str, quantity: int) -> str:
#     "Add an item to the inventory."
#     inventory_db[sku] = {{"name": name, "quantity": quantity}}
#     return f"Added {{name}} (SKU: {{sku}}, qty: {{quantity}}) to inventory."
#
# Any agent that manages data (inventory, orders, tasks) MUST use a module-level
# dict or list as the data store, and tools MUST read/write that store directly.

## STATE FIELDS MUST BE USED — NO DEAD STATE
# If you declare a field in AgentState, it MUST be read or written somewhere.
# Dead fields like `inventory: dict` that are never touched are bugs, not features.
#
# WRONG:
# class AgentState(TypedDict):
#     messages: Annotated[List[BaseMessage], operator.add]
#     inventory: dict   <- declared but never read or written
#
# CORRECT — if you need per-session data, store it in a module-level dict keyed by thread_id:
# _sessions: dict = {{}}
# def get_session(thread_id: str) -> dict:
#     if thread_id not in _sessions:
#         _sessions[thread_id] = {{"inventory": {{}}}}
#     return _sessions[thread_id]

## ALL NODES MUST BE REGISTERED IN THE GRAPH
# Every function you define as a node MUST be added with workflow.add_node().
# An unregistered node function is dead code — it will never run.
#
# WRONG:
# async def tool_processor(state): ...   <- defined but never registered
#
# CORRECT — register every node:
# workflow.add_node("tool_processor", tool_processor)
# workflow.add_edge("chatbot", "tool_processor")

## GRAPH CONSTRUCTION — NEVER USE @ DECORATOR SYNTAX ON WORKFLOW METHODS
# workflow.add_node(), workflow.add_edge(), workflow.add_conditional_edges()
# are plain method CALLS. They are NOT decorators.
# Using @ on them is a SyntaxError that reports on the NEXT valid line, making
# it very hard to trace.
#
# WRONG — SyntaxError (reported on the line after):
# @workflow.add_conditional_edges("chatbot", route_fn)
# @workflow.add_node("tools", ToolNode(tools))
# workflow.add_edge("tools", "chatbot")   <- error reported here, not above
#
# CORRECT — call them as plain statements:
# workflow.add_node("chatbot", chatbot_node)
# workflow.add_node("tools", ToolNode(tools))
# workflow.set_entry_point("chatbot")
# workflow.add_conditional_edges("chatbot", route_fn, {{"tools": "tools", END: END}})
# workflow.add_edge("tools", "chatbot")

## GRAPH ENTRYPOINT — set_entry_point IS MANDATORY
# Every graph MUST have an entrypoint or workflow.compile() raises:
# ValueError: Graph must have an entrypoint: add at least one edge from START to another node
#
# ALWAYS call this before compile():
# workflow.set_entry_point("chatbot")   <- or whatever your first node is named
#
# WRONG — missing entrypoint, crashes at compile time:
# workflow.add_node("chatbot", chatbot_node)
# workflow.add_node("tools", ToolNode(tools))
# workflow.add_conditional_edges("chatbot", route_after_chatbot, ...)
# workflow.compile()   <- ValueError
#
# CORRECT:
# workflow.add_node("chatbot", chatbot_node)
# workflow.add_node("tools", ToolNode(tools))
# workflow.set_entry_point("chatbot")   <- MUST be present
# workflow.add_conditional_edges("chatbot", route_after_chatbot, ...)
# workflow.compile()   <- OK

## GRAPH EDGES — CONDITIONAL AND DIRECT EDGES MUST NOT CONFLICT
# Do NOT add both a conditional edge AND a direct edge from the same node.
# The direct edge will override or conflict with the conditional router.
#
# WRONG:
# workflow.add_conditional_edges("chatbot", route_after_chatbot, {{"tools": "tools", END: END}})
# workflow.add_edge("chatbot", END)   <- contradicts the conditional edge above
#
# CORRECT — use one or the other, never both from the same source node:
# workflow.add_conditional_edges("chatbot", route_after_chatbot, {{"tools": "tools", END: END}})

## THREAD_ID MUST BE USED FOR SESSION ISOLATION
# If your request model has thread_id, it MUST be passed into the graph config
# AND used inside tools to isolate state per user/session.
#
# WRONG:
# def get_initial_state(thread_id):   <- thread_id taken but ignored
#     return {{"messages": []}}
#
# CORRECT:
# config = {{"configurable": {{"thread_id": request.thread_id}}}}
# result = app_graph.invoke(initial_state, config=config)
# Inside tools, retrieve per-session data using thread_id from the context.

## SEARCH TOOLS INSIDE OTHER TOOLS — ADD CALL LIMITS
# Wrapping an external search tool (Tavily) inside a @tool function can cause
# the LLM to call it in a tight loop. Always add a result limit and make the
# tool description clear about what it returns so the LLM stops after one call.
# search_tool = TavilySearch(max_results=3)   <- cap results to avoid runaway calls

## LOGGING — MANDATORY in every agent.py
import logging
logging.basicConfig(level=logging.INFO, format="[%%(levelname)s] %%(message)s")
log = logging.getLogger(__name__)
# In chatbot_node, always log the response object directly — never state["messages"]:
# log.info(f"tool_calls: {{getattr(response, 'tool_calls', [])}}")
# log.info(f"content: {{response.content!r}}")

## F-STRINGS — BACKSLASH ESCAPES INSIDE {{}} ARE A SYNTAX ERROR
# Python does not allow backslash escapes inside f-string expressions.
# This is a SyntaxError in ALL Python versions:
#
# WRONG — SyntaxError: unexpected character after line continuation character:
# log.info(f"tool_calls: {{getattr(state[\"messages\"][-1], 'tool_calls', [])}}")
#
# CORRECT — assign to a variable first, then use it in the f-string:
# last_msg = state["messages"][-1]
# log.info(f"tool_calls: {{getattr(last_msg, 'tool_calls', [])}}")
#
# CORRECT — use single quotes for the outer string so inner double quotes work:
# log.info(f'tool_calls: {{getattr(state["messages"][-1], "tool_calls", [])}}')
#
# RULE: if you need to index into state inside an f-string, extract the value
# into a variable BEFORE the f-string. Never use \" inside f-string {{}}.

## STATE — use Annotated + operator.add for messages
from typing import Annotated
import operator
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

## GENERAL PYTHON RULES
- NEVER repeat the same keyword argument in a function call — Python raises SyntaxError
- BAD:  TavilySearch(max_results=3, max_results=3)
- GOOD: TavilySearch(max_results=3)

## FASTAPI REQUEST MODEL
class AgentRequest(BaseModel):
    user_input: str
    thread_id: str

## FASTAPI BOILERPLATE — COPY THIS EXACTLY INTO EVERY agent.py
# These 4 imports + app setup + CORS + UI route are NON-NEGOTIABLE.
# Missing any part causes browser blocks or 404 on the UI.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

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

# Rules:
# - CORS middleware MUST come immediately after app = FastAPI() and before any routes
# - open() MUST use encoding="utf-8" — Windows default (cp1252) crashes on any non-ASCII char
# - The "/" route MUST be present — without it the browser UI returns 404

## .env CONTENTS
OPENROUTER_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here

## ui.html REQUIREMENTS
- Pure HTML + CSS + JS in one file, zero CDN, zero frameworks
- POST to http://127.0.0.1:8000/run
- JSON body: {{ user_input: inputValue, thread_id: "thread-1" }}
- Show spinner while loading, disable Submit button during request
- Show red error message if fetch fails or status != 200

## ui.html RESPONSE RENDERING — MANDATORY
# Agent replies often contain markdown (bold, headers, line breaks).
# Raw text displayed with .textContent loses all formatting.
# ALWAYS include this parseMarkdown function and use it when rendering replies:

function parseMarkdown(text) {{
  return text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}}

# ALWAYS render agent replies with innerHTML via parseMarkdown, NOT textContent:
# WRONG  — strips all formatting:
#   bubble.textContent = data.assistant_reply;
# CORRECT — renders markdown properly:
#   bubble.innerHTML = parseMarkdown(data.assistant_reply);
#
# Inside sendMessage, the call must be:
#   addBubble(parseMarkdown(data.assistant_reply), 'agent');
#
# addBubble must use innerHTML to insert the parsed content:
# function addBubble(html, role) {{
#   const div = document.createElement('div');
#   div.className = `bubble ${{role}}`;
#   div.innerHTML = html;           // <-- innerHTML, not textContent
#   chatWindow.appendChild(div);
#   chatWindow.scrollTop = chatWindow.scrollHeight;
# }}
---


## STANDARDS
## DEV STANDARDS
{dev_standards if dev_standards else "None"}

## UI STANDARDS — follow these exactly when generating ui.html
{ui_standards if ui_standards else "None"}

{realtime_block}
""")

    # Only pass the latest human message — not full history.
    # Full history makes the LLM think the job is already done.
    human_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    last_human = human_messages[-1:] if human_messages else state["messages"][-1:]

    bound_llm = llm.bind_tools(coder_tools, tool_choice="required")
    MAX_ATTEMPTS = 5
    all_tool_calls = []   # accumulate across every attempt
    last_response = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print("🚀 Entering coder_node")

        response = bound_llm.invoke([system] + last_human)
        last_response = response

        new_calls = response.tool_calls or []
        all_tool_calls.extend(new_calls)

        # Deduplicate by filename — keep the last version if the same file appears twice
        seen = {}
        for tc in all_tool_calls:
            fname = tc["args"].get("filename", "").split("/")[-1]
            seen[fname] = tc
        all_tool_calls = list(seen.values())

        filenames_so_far = [tc["args"].get("filename", "?") for tc in all_tool_calls]
        print(f"[coder] attempt {attempt}: +{len(new_calls)} call(s) | total so far → {filenames_so_far}")

        saved_basenames = {tc["args"].get("filename", "").split("/")[-1] for tc in all_tool_calls}
        missing = [f for f in ["agent.py", ".env", "ui.html"] if f not in saved_basenames]

        if not missing:
            print("[coder] All 3 files accumulated.")
            break

        if attempt < MAX_ATTEMPTS:
            print(f"[coder] Still missing: {missing} — retrying...")
            retry_msg = HumanMessage(content=(
                f"You still need to generate: {missing}. "
                f"Call save_code_to_file for EACH missing file RIGHT NOW. "
                f"Do not repeat files already done. Do not explain. Just call the tool."
            ))
            last_human = last_human + [AIMessage(content="", tool_calls=new_calls), retry_msg]

    print(f"[coder] Final accumulated tool_calls: {len(all_tool_calls)}")

    # ── Normalise tool calls before packing into AIMessage ────────────────
    # Groq sometimes returns tool_calls without an 'id' or 'type' field.
    # ToolNode uses tc['name'] to look up the tool, and tc['id'] to correlate
    # ToolMessages back to the AIMessage. Both MUST be present and non-None.
    import uuid
    normalised = []
    for tc in all_tool_calls:
        normalised.append({
            "name": tc.get("name") or "save_code_to_file",
            "args": tc.get("args", {}),
            "id":   tc.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            "type": tc.get("type") or "tool_call",
        })

    print(f"[coder] Normalised tool_calls: {[t['name'] for t in normalised]}")

    # Build one AIMessage carrying all accumulated tool calls
    final_message = AIMessage(
        content=last_response.content if last_response else "",
        tool_calls=normalised,
    )
    return {"messages": [final_message]}


def import_fixer_node(state: AgentState) -> dict:
    """Deterministic fix — corrects bad imports and patterns before code hits disk."""
    last = state["messages"][-1]

    if not hasattr(last, "tool_calls") or not last.tool_calls:
        print("[import_fixer] No tool calls to scan.")
        return {}

    fixed_tool_calls, all_changes = fix_code_in_tool_calls(last.tool_calls)

    if all_changes:
        print(f"[import_fixer] Fixed {len(all_changes)} issue(s):")
        for change in all_changes:
            print(change)
        fixed_message = AIMessage(
            content=last.content,
            tool_calls=fixed_tool_calls,
        )
        return {"messages": [fixed_message]}

    print("[import_fixer] All imports look correct.")
    return {}


def validator_node(state: AgentState) -> dict:
    """Validates agent.py files for banned patterns and missing required blocks."""
    last = state["messages"][-1]

    if not hasattr(last, "tool_calls"):
        return {}

    all_issues = []

    for tc in last.tool_calls:
        args = tc.get("args", {})
        if "code" not in args:
            continue
        filename = args.get("filename", "")
        issues = validate_generated_code(args["code"], filename)
        if issues:
            all_issues.extend([f"{filename}: {issue}" for issue in issues])

    if all_issues:
        print("\n[validator] Issues detected:")
        for issue in all_issues:
            print(f"  - {issue}")
    else:
        print("[validator] Passed.")

    return {}


def runtime_check_node(state):
    # code_tools leaves a ToolMessage as the last message — walk back to find
    # the AIMessage that carries the tool_calls with the filenames.
    ai_message = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            ai_message = msg
            break

    if not ai_message:
        print("[runtime_check] No AIMessage with tool_calls found — skipping.")
        return {}

    all_passed = True
    checked_any = False
    agent_dir = None  # folder containing agent.py + its .env/ui.html

    for tc in ai_message.tool_calls:
        filename = tc["args"].get("filename", "")
        if not filename.endswith("agent.py"):
            continue

        # Strip the generated_agents/ prefix if the tool stored it that way
        clean = filename
        for prefix in ["generated_agents/", "generated_agents\\"]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break

        path = os.path.abspath(os.path.join(settings.generated_agents_dir, clean))

        if not os.path.exists(path):
            print(f"[runtime_check] File not found, skipping: {path}")
            continue

        checked_any = True
        agent_dir = os.path.dirname(path)

        # Syntax-check only — never execute the file (would start a server on port 8000)
        try:
            import py_compile
            py_compile.compile(path, doraise=True)
            print(f"[runtime_check] PASS — {path} is syntactically valid.")
        except py_compile.PyCompileError as e:
            print(f"[runtime_check] SYNTAX ERROR in {path}: {e}")
            all_passed = False
        except Exception as e:
            print(f"[runtime_check] EXCEPTION checking {path}: {e}")
            all_passed = False

    if not (checked_any and all_passed and agent_dir):
        return {}

    # ── Persist only on a clean pass ────────────────────────────────────────
    # agent_dir's basename IS the canonical agent name — it's the exact folder
    # coder_node locked via set_canonical_agent_name(), so no separate lookup
    # is needed here.
    canonical_name = os.path.basename(agent_dir)
    spec = state.get("agent_spec")
    display_name = getattr(spec, "agent_name", None) or canonical_name
    realtime_config = state.get("realtime_config")
    category = realtime_config.get("category", "none") if realtime_config else "none"

    # Build rich metadata so the DB is actually useful for context retrieval
    metadata = {
        "model_used": "openai/gpt-oss-120b:free",
        "task_type": getattr(spec, "task_type", "code_gen"),
        "frontend_type": getattr(spec, "frontend_type", "chat"),
        "tools_needed": list(getattr(spec, "tools_needed", []) or []),
    }
    if realtime_config:
        metadata["realtime_api"] = realtime_config.get("api_name", "")
        metadata["realtime_key_var"] = realtime_config.get("key_env_var", "")
        metadata["realtime_base_url"] = realtime_config.get("base_url", "")

    try:
        existing = get_agent_by_canonical_name(canonical_name)
        if existing:
            new_version = save_new_version(
                agent_id=existing["id"],
                source_code_dir=agent_dir,
                prompt_used=state.get("query", ""),
            )
            print(f"[runtime_check] Updated existing agent {existing['id']} -> v{new_version}")
            return {"agent_id": existing["id"]}

        agent_id = save_agent(
            canonical_name=canonical_name,
            display_name=display_name,
            original_prompt=state.get("query", ""),
            category=category,
            source_code_dir=agent_dir,
            metadata=metadata,
        )
        print(f"[runtime_check] Saved NEW agent — id={agent_id} category={category}")
        return {"agent_id": agent_id}
    except Exception as e:
        print(f"[runtime_check] Persistence save failed: {e}")
        return {}

# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_supervisor(state: AgentState) -> str:
    return state["next_agent"]


def route_after_researcher(state: AgentState) -> str:
    last = state["messages"][-1]
    return "research_tools" if getattr(last, "tool_calls", None) else END


def route_after_coder(state: AgentState) -> str:
    last = state["messages"][-1]
    return "import_fixer" if getattr(last, "tool_calls", None) else END


def route_after_fixer(state: AgentState) -> str:
    last = state["messages"][-1]
    return "validator" if getattr(last, "tool_calls", None) else END


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

memory = MemorySaver()

workflow = StateGraph(AgentState)

workflow.add_node("parser",             parser_node)
workflow.add_node("realtime_detector",  realtime_detector_node)   # ← add here
workflow.add_node("supervisor",         supervisor_node)
workflow.add_node("researcher",         research_node)
workflow.add_node("coder",              coder_node)
workflow.add_node("import_fixer",       import_fixer_node)
workflow.add_node("validator",          validator_node)
workflow.add_node("runtime_check",      runtime_check_node)
workflow.add_node("research_tools",     ToolNode(research_tools, handle_tool_errors=True))
workflow.add_node("code_tools",         ToolNode(coder_tools,   handle_tool_errors=True))

workflow.set_entry_point("parser")

# parser → realtime_detector → supervisor  (was parser → supervisor)
workflow.add_edge("parser",            "realtime_detector")        # ← changed
workflow.add_edge("realtime_detector", "supervisor")               # ← new

# Supervisor routes to coder or researcher
workflow.add_conditional_edges("supervisor", route_after_supervisor)

# Researcher loop — exits when LLM stops calling tools
workflow.add_conditional_edges("researcher", route_after_researcher)
workflow.add_edge("research_tools", "researcher")

# Coder pipeline — LINEAR, no loop back
workflow.add_conditional_edges("coder",        route_after_coder)  # → import_fixer or END
workflow.add_conditional_edges("import_fixer", route_after_fixer)  # → validator or END
workflow.add_edge("validator",     "code_tools")
workflow.add_edge("code_tools",    "runtime_check")
workflow.add_edge("runtime_check", END)

app_graph = workflow.compile(checkpointer=memory)