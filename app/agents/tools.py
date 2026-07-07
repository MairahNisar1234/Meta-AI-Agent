_canonical_agent_name: str | None = None
from langchain_core.tools import tool
from app.core.config import settings
from app.agents.code_fixes import fix_imports, fix_code_patterns, validate_generated_code
import os
# At the top of coder_tools.py — module-level variable


def set_canonical_agent_name(name: str):
    """Called by coder_node before invoking tools, sets the authoritative name."""
    global _canonical_agent_name
    _canonical_agent_name = name

def _extract_agent_name(filename: str) -> str:
    # ✅ use canonical name if set — ignore whatever folder the LLM invented
    if _canonical_agent_name:
        return _canonical_agent_name
    parts = filename.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[0]
    return "current_agent"



@tool
def save_code_to_file(filename: str, code: str) -> str:
    """
    Save generated code to a file inside the generated_agents directory.
    Automatically fixes bad imports and validates before writing.

    Args:
        filename: Relative path such as 'agent.py' or 'cricket_bot/agent.py'
        code: Complete file contents to write

    Returns:
        Confirmation message containing the saved file path.
    """
    filename = filename.replace("\\", "/")

    # Strip any accidental 'generated_agents/' prefix the LLM might add
    for prefix in ["generated_agents/", "generated_agents\\"]:
        if filename.startswith(prefix):
            filename = filename[len(prefix):]

    # ── Fix imports (line-by-line) ────────────────────────────────────────────
    code, import_changes = fix_imports(code)
    if import_changes:
        print(f"[save_tool] Fixed {len(import_changes)} import(s) in {filename}:")
        for c in import_changes:
            print(c)

    # ── Fix code patterns (regex) ─────────────────────────────────────────────
    code, pattern_changes = fix_code_patterns(code)
    if pattern_changes:
        print(f"[save_tool] Fixed {len(pattern_changes)} pattern(s) in {filename}:")
        for c in pattern_changes:
            print(c)

    # ── Validate ──────────────────────────────────────────────────────────────
    issues = validate_generated_code(code, filename)
    if issues:
        print(f"[save_tool] Validation issues in {filename}:")
        for issue in issues:
            print(f"  ⚠ {issue}")

    # ── Write to disk ─────────────────────────────────────────────────────────
    path = os.path.join(settings.generated_agents_dir, filename)
    path = os.path.abspath(path)

    print(f"[SAVE] Writing to: {path}")

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

    exists = os.path.exists(path)

    # ── Copy realtime .env if it exists in staging folder ────────────────────
    # realtime_detector may have written to current_agent/ before agent_name
    # was known. If so, move those vars into the real agent folder now.
    agent_name  = _extract_agent_name(filename)
    agent_dir   = os.path.join(settings.generated_agents_dir, agent_name)
    staging_env = os.path.join(settings.generated_agents_dir, "current_agent", ".env")
    target_env  = os.path.join(agent_dir, ".env")

    if (
        agent_name != "current_agent"
        and os.path.exists(staging_env)
        and not os.path.exists(target_env)
    ):
        os.makedirs(agent_dir, exist_ok=True)
        import shutil
        shutil.copy2(staging_env, target_env)
        print(f"[save_tool] Moved realtime .env → {target_env}")

    summary = f"Saved to {path}. Exists={exists}"

    if import_changes or pattern_changes:
        summary += f" | Fixed: {len(import_changes)} imports, {len(pattern_changes)} patterns"
    if issues:
        summary += f" | Warnings: {len(issues)}"

    return summary


@tool
def verify_agent_code(agent_name: str) -> str:
    """Runs a dry-run check of the generated agent.py to catch syntax errors."""
    path = os.path.join(settings.generated_agents_dir, agent_name, "agent.py")
    try:
        import py_compile
        py_compile.compile(path, doraise=True)
        return "SUCCESS: Code is syntactically valid."
    except Exception as e:
        return f"CRITICAL ERROR: Code failed to compile. Error: {str(e)}"