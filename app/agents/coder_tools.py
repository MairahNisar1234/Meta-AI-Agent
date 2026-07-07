from langchain_core.tools import tool
from app.core.config import settings
from app.agents.code_fixes import fix_imports, fix_code_patterns, validate_generated_code
import os

# ── Canonical agent name — set by coder_node before LLM runs ─────────────────
# This prevents the LLM from inventing a different folder name than the parser set.
_canonical_agent_name: str | None = None

def set_canonical_agent_name(name: str) -> None:
    """
    Called by coder_node BEFORE invoking the LLM.
    Locks in the authoritative agent folder name from agent_spec.agent_name
    so save_code_to_file always writes to the correct folder regardless of
    what folder name the LLM invents.
    """
    global _canonical_agent_name
    _canonical_agent_name = name
    print(f"[coder_tools] Canonical agent name locked: {name}")

def reset_canonical_agent_name() -> None:
    """Call at the start of each request to prevent stale names from leaking across requests."""
    global _canonical_agent_name
    _canonical_agent_name = None

def get_canonical_agent_name() -> str | None:
    return _canonical_agent_name

# ─────────────────────────────────────────────────────────────────────────────

def _extract_agent_name(filename: str) -> str:
    """
    Returns the agent folder name to use.
    Priority:
      1. _canonical_agent_name  (set by coder_node from agent_spec — always correct)
      2. folder portion of filename  (fallback — may be wrong if LLM invented it)
      3. "current_agent"  (last resort)
    """
    if _canonical_agent_name:
        return _canonical_agent_name
    parts = filename.replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[0]
    return "current_agent"


def _enforce_canonical_filename(filename: str) -> str:
    """
    Rewrites the folder portion of filename to use the canonical agent name.
    Examples (canonical = 'cricket_score_agent'):
      'cricket_assistant/agent.py' -> 'cricket_score_agent/agent.py'
      'agent.py'                   -> 'cricket_score_agent/agent.py'
      'cricket_score_agent/ui.html'-> 'cricket_score_agent/ui.html'  (unchanged)
    """
    if not _canonical_agent_name:
        return filename

    filename = filename.replace("\\", "/")
    parts = filename.split("/")

    if len(parts) >= 2:
        if parts[0] != _canonical_agent_name:
            print(f"[coder_tools] Folder override: '{parts[0]}' -> '{_canonical_agent_name}'")
            parts[0] = _canonical_agent_name
        return "/".join(parts)
    else:
        # flat filename like 'agent.py' — prepend canonical folder
        return f"{_canonical_agent_name}/{filename}"


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

    # ── Enforce canonical folder name — override whatever the LLM invented ───
    filename = _enforce_canonical_filename(filename)

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

    # ── Special handling for .env — MERGE, never overwrite ───────────────────
    # realtime_detector writes API keys into the .env before the LLM runs.
    # If we blindly overwrite, those keys are lost. Instead: keep any existing
    # keys and only add keys that aren't already present.
    if filename.endswith(".env") and os.path.exists(path):
        from dotenv import dotenv_values
        existing_vars = dotenv_values(path)
        if existing_vars:
            # Parse the new content the LLM produced
            new_vars: dict = {}
            for line in code.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    new_vars[k.strip()] = v.strip()

            # Merge: existing keys win (they have real values or detector-set vars)
            merged = {**new_vars, **existing_vars}  # existing_vars overrides new_vars

            # Reconstruct the file — existing keys first, then any new-only keys
            lines = []
            # Write all existing keys (preserves detector vars + any real keys)
            for k, v in existing_vars.items():
                lines.append(f"{k}={v}")
            # Append keys from LLM that weren't already there
            for k, v in new_vars.items():
                if k not in existing_vars:
                    lines.append(f"{k}={v}")

            code = "\n".join(lines) + "\n"
            print(f"[SAVE] .env merged — kept {len(existing_vars)} existing vars, added {len(merged) - len(existing_vars)} new")

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

    exists = os.path.exists(path)

    # ── Merge realtime .env from staging folder if needed ────────────────────
    # realtime_detector writes to <canonical_name>/.env before coder runs.
    # If it fell back to current_agent/ staging, move it to the real folder now.
    agent_name   = _extract_agent_name(filename)
    agent_dir    = os.path.join(settings.generated_agents_dir, agent_name)
    realtime_env = os.path.join(settings.generated_agents_dir, agent_name, ".env")
    staging_env  = os.path.join(settings.generated_agents_dir, "current_agent", ".env")

    if (
        agent_name != "current_agent"
        and os.path.exists(staging_env)
        and not os.path.exists(realtime_env)
    ):
        os.makedirs(agent_dir, exist_ok=True)
        import shutil
        shutil.copy2(staging_env, realtime_env)
        print(f"[save_tool] Moved staged realtime .env -> {realtime_env}")

    summary = f"Saved to {path}. Exists={exists}"
    if import_changes or pattern_changes:
        summary += f" | Fixed: {len(import_changes)} imports, {len(pattern_changes)} patterns"
    if issues:
        summary += f" | Warnings: {len(issues)}"

    return summary


@tool
def verify_agent_code(agent_name: str) -> str:
    """Runs a dry-run syntax check of the generated agent.py. Never executes it."""
    path = os.path.join(settings.generated_agents_dir, agent_name, "agent.py")
    try:
        import py_compile
        py_compile.compile(path, doraise=True)
        return "SUCCESS: Code is syntactically valid."
    except Exception as e:
        return f"CRITICAL ERROR: Code failed to compile. Error: {str(e)}"