from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.schema import AgentSpec
from app.core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
#from langchain_groq import ChatGroq
import json, re

#llm = ChatOpenRouter(model="openai/gpt-oss-120b:free")
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.gemini_api_key,
    temperature=0,
)

BUILD_KEYWORDS = ["agent", "build", "create", "make", "generate",
                  "tool", "app", "bot", "assistant", "tracker",
                  "manager", "planner", "system", "dashboard"]

PARSER_PROMPT = """You are an intent classifier. Given a user query, output ONLY a JSON object — no explanation, no markdown, no backticks.

Rules:
- If the query asks to BUILD, CREATE, MAKE, or GENERATE any agent, app, tool, bot, assistant, tracker, manager, planner → task_type: "code_gen"
- If the query ONLY asks to research or find facts → task_type: "research"
- When in doubt → task_type: "code_gen"
- requires_web_search: true only if live data or news is needed
- frontend_type: one of "chat", "dashboard", "form", "results"
- tools_needed: list from ["tavily_search", "save_code_to_file", "calculator", "code_executor", "file_reader"]
- agent_name: snake_case short name e.g. "travel_planner"
- reasoning: one sentence explaining your classification

Return exactly this shape:
{
  "agent_name": "...",
  "task_type": "code_gen",
  "requires_web_search": false,
  "tools_needed": ["save_code_to_file"],
  "description": "...",
  "frontend_type": "chat",
  "reasoning": "User wants to build an agent therefore code_gen."
}"""


def _default_spec(query: str) -> AgentSpec:
    words = query.lower().split()
    name = "_".join(w for w in words[:3] if w.isalpha()) or "new_agent"
    return AgentSpec(
        agent_name=name,
        task_type="code_gen",
        requires_web_search=False,
        tools_needed=["save_code_to_file"],
        frontend_type="chat",
        reasoning="Defaulted to code_gen — parser fallback.",
    )


def parse_query_to_spec(query: str) -> AgentSpec:
    try:
        print("🚀 Entering parser.py_node")
        response = llm.invoke([
            SystemMessage(content=PARSER_PROMPT),
            HumanMessage(content=query)
        ])

        raw = response.content.strip()

        # Strip markdown fences if model wraps in ```json ... ```
        raw = re.sub(r"^```[\w]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

        data = json.loads(raw)

        # Filter tools_needed to only valid literals
        valid_tools = {"tavily_search", "save_code_to_file", "calculator", "code_executor", "file_reader"}
        tools = [t for t in data.get("tools_needed", []) if t in valid_tools]
        if not tools:
            tools = ["save_code_to_file"]

        spec = AgentSpec(
            agent_name=data.get("agent_name", "new_agent"),
            task_type=data.get("task_type", "code_gen"),
            requires_web_search=data.get("requires_web_search", False),
            tools_needed=tools,
            frontend_type=data.get("frontend_type", "chat"),
            reasoning=data.get("reasoning", "Parsed from query."),
        )

    except Exception as e:
        print(f"[parser] failed to parse LLM response: {e} — using default")
        spec = _default_spec(query)

    # Safety override — build keywords always force code_gen
    if any(word in query.lower() for word in BUILD_KEYWORDS):
        if spec.task_type != "code_gen":
            print(f"[parser] overriding '{spec.task_type}' → 'code_gen'")
            spec.task_type = "code_gen"

    print(f"[parser] task_type={spec.task_type} | agent_name={spec.agent_name} | frontend={spec.frontend_type}")
    return spec