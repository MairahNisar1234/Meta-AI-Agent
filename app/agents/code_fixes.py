import re
import os
import sys
import subprocess
import tempfile
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Import correction map
# ---------------------------------------------------------------------------

IMPORT_CORRECTIONS = {
    "from langchain_openai import ChatOpenAI": "from langchain_openrouter import ChatOpenRouter  # replaced ChatOpenAI",
    "from langchain_openai import OpenAI": "from langchain_openrouter import ChatOpenRouter  # replaced OpenAI",
    "from langchain.chat_models import ChatOpenAI": "from langchain_openrouter import ChatOpenRouter  # replaced ChatOpenAI",
    "from langchain.llms import OpenAI": "from langchain_openrouter import ChatOpenRouter  # replaced OpenAI",
    "from langchain_community.tools.tavily_search import TavilySearchResults": "from langchain_tavily import TavilySearch",
    "from langchain.tools import TavilySearchResults": "from langchain_tavily import TavilySearch",
    "from langchain.schema import HumanMessage": "from langchain_core.messages import HumanMessage",
    "from langchain.schema import AIMessage": "from langchain_core.messages import AIMessage",
    "from langchain.schema import SystemMessage": "from langchain_core.messages import SystemMessage",
    "from pydantic import BaseSettings": "from pydantic_settings import BaseSettings, SettingsConfigDict",
    "from langchain_core.pydantic_v1 import BaseModel": "from pydantic import BaseModel",
    "from langchain_core.pydantic_v1 import":           "from pydantic import",
    "from langchain.pydantic_v1 import BaseModel":      "from pydantic import BaseModel",
    "from langchain.pydantic_v1 import":                "from pydantic import",
}

# ---------------------------------------------------------------------------
# Regex pattern fixes
# ---------------------------------------------------------------------------

CODE_PATTERN_FIXES = [
    (r'ChatOpenAI\s*\(', 'ChatOpenRouter('),
    (r'\bTavilySearchResults\s*\(', 'TavilySearch('),
    (r'\bOPENAI_API_KEY\b', 'OPENROUTER_API_KEY'),
    # Fix open("ui.html", "r") missing encoding — causes UnicodeDecodeError on Windows (cp1252)
    (r'open\(["\']ui\.html["\'],\s*["\']r["\']\)', 'open("ui.html", "r", encoding="utf-8")'),
]

# ---------------------------------------------------------------------------
# IMPORT FIXER
# ---------------------------------------------------------------------------

def fix_imports(code: str) -> Tuple[str, List[str]]:
    lines = code.split("\n")
    fixed_lines = []
    changes = []

    for line in lines:
        stripped = line.strip()
        corrected = line

        for wrong, right in IMPORT_CORRECTIONS.items():
            if stripped.startswith(wrong):
                corrected = right
                changes.append(f"✗ {stripped} -> ✓ {right}")
                break

        fixed_lines.append(corrected)

    return "\n".join(fixed_lines), changes

# ---------------------------------------------------------------------------
# PATTERN FIXER
# ---------------------------------------------------------------------------

def fix_code_patterns(code: str) -> Tuple[str, List[str]]:
    changes = []

    for pattern, replacement in CODE_PATTERN_FIXES:
        if re.search(pattern, code):
            code, count = re.subn(pattern, replacement, code)
            if count:
                changes.append(f"regex fixed {count}x: {pattern}")

    return code, changes

# ---------------------------------------------------------------------------
# RUNTIME VALIDATOR (NEW 🔥)
# ---------------------------------------------------------------------------

def runtime_validate_code(code: str, filename: str = "agent.py") -> List[str]:
    """
    Executes syntax + import check in isolated temp environment.
    This catches REAL runtime errors (NameError, ImportError, etc.)
    """

    issues = []

    if not filename.endswith(".py"):
        return issues

    try:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "test_agent.py")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)

            # 1. Syntax check
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                issues.append(f"SYNTAX ERROR:\n{result.stderr}")

            # 2. Runtime import execution (safe sandbox)
            result2 = subprocess.run(
                [sys.executable, file_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result2.returncode != 0:
                issues.append(f"RUNTIME ERROR:\n{result2.stderr}")

    except subprocess.TimeoutExpired:
        issues.append("TIMEOUT ERROR: code execution took too long")
    except Exception as e:
        issues.append(f"VALIDATOR CRASH: {str(e)}")

    return issues

# ---------------------------------------------------------------------------
# TOOL CALL FIXER
# ---------------------------------------------------------------------------

def fix_code_in_tool_calls(tool_calls: list) -> Tuple[list, List[str]]:
    fixed_tool_calls = []
    all_changes: List[str] = []

    for tc in tool_calls:
        args = dict(tc.get("args", {}))

        if "code" in args:
            code, imp_changes = fix_imports(args["code"])
            code, pat_changes = fix_code_patterns(code)

            args["code"] = code
            all_changes.extend(imp_changes)
            all_changes.extend(pat_changes)

        fixed_tool_calls.append({**tc, "args": args})

    return fixed_tool_calls, all_changes

# ---------------------------------------------------------------------------
# FINAL VALIDATOR (UPDATED 🔥)
# ---------------------------------------------------------------------------

def validate_generated_code(code: str, filename: str = "") -> List[str]:
    issues = []

    # ------------------------
    # ui.html checks
    # ------------------------
    if filename.endswith("ui.html"):
        if "parseMarkdown" not in code:
            issues.append(
                "Missing parseMarkdown() — agent replies lose all markdown formatting. "
                "Add the function and call addBubble(parseMarkdown(data.assistant_reply), 'agent')"
            )
        if "assistant_reply" in code and "innerHTML" not in code:
            issues.append(
                "assistant_reply rendered without innerHTML — use innerHTML not textContent "
                "so parseMarkdown output is displayed correctly"
            )
        return issues

    if not filename.endswith("agent.py"):
        return issues

    # ------------------------
    # STATIC CHECKS
    # ------------------------

    if "load_dotenv()" not in code:
        issues.append("Missing load_dotenv()")

    if "CORSMiddleware" not in code:
        issues.append("Missing CORS middleware")

    if "@app.get(\"/\")" not in code and "@app.get('/')" not in code:
        issues.append("Missing UI route")

    # open("ui.html") without encoding="utf-8" crashes on Windows with UnicodeDecodeError
    if re.search(r'open\s*\(\s*["\']ui\.html["\'](?!\s*,\s*["\']r["\']?\s*,\s*encoding)', code):
        if 'open("ui.html"' in code or "open('ui.html'" in code:
            issues.append(
                "BANNED: open('ui.html', 'r') missing encoding='utf-8' — "
                "crashes on Windows with UnicodeDecodeError. "
                "Use: open('ui.html', 'r', encoding='utf-8')"
            )

    if "ToolNode(" in code and "@tool" not in code:
        issues.append("ToolNode used without @tool decorator")

    if "workflow.add_node(" in code and "workflow.set_entry_point(" not in code:
        issues.append(
            "BANNED: workflow.set_entry_point() is missing — "
            "workflow.compile() will raise ValueError: Graph must have an entrypoint"
        )

    if "ChatOpenAI" in code:
        issues.append("BANNED: ChatOpenAI used instead of ChatOpenRouter")

    # Backslash escapes inside f-string expressions are a SyntaxError
    if re.search(r'f["\'].*\{[^}]*\\["\'][^}]*\}', code):
        issues.append(
            'BANNED: backslash escape inside f-string expression — SyntaxError. '
            'Extract the value to a variable before the f-string instead of using \\" inside {}'
        )

    # @ decorator syntax on workflow method calls is a SyntaxError
    if re.search(r'^@workflow\.(add_node|add_edge|add_conditional_edges|set_entry_point)', code, re.MULTILINE):
        issues.append(
            'BANNED: @workflow.add_node / @workflow.add_edge used as decorator — SyntaxError. '
            'These are plain method calls, not decorators. Remove the @ prefix.'
        )
    if "TavilySearchResults" in code:
        issues.append("BANNED: TavilySearchResults is deprecated")

    if "OPENAI_API_KEY" in code:
        issues.append("BANNED: Must use OPENROUTER_API_KEY")

    if "langchain_core.pydantic_v1" in code or "langchain.pydantic_v1" in code:
        issues.append(
            "BANNED: langchain_core.pydantic_v1 / langchain.pydantic_v1 no longer exist — "
            "ModuleNotFoundError at runtime. Use: from pydantic import BaseModel, Field"
        )

    # ------------------------
    # RUNTIME CHECK (🔥 NEW)
    # ------------------------

    runtime_issues = runtime_validate_code(code, filename)
    issues.extend(runtime_issues)

    return issues

# ---------------------------------------------------------------------------
# FILE READER — call after all files are confirmed saved
# ---------------------------------------------------------------------------

def read_generated_files(base_dir: str = ".") -> dict:
    """
    Reads agent.py, .env, ui.html from disk after the coder node saves them.
    Returns a dict safe to merge into AgentState.
    """
    contents = {"agent_py": "", "env": "", "ui_html": ""}

    file_map = {
        "agent.py": "agent_py",
        ".env":     "env",
        "ui.html":  "ui_html",
    }

    for filename, state_key in file_map.items():
        path = os.path.join(base_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                contents[state_key] = f.read()
        except FileNotFoundError:
            contents[state_key] = ""
        except Exception as e:
            contents[state_key] = f"# ERROR reading {filename}: {e}"

    return contents