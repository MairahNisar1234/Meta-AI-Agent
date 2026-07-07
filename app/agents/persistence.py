"""
persistence.py

Drop-in persistence layer for the meta-agent system.

What it does:
- Stores metadata about every generated agent in SQLite (agents.db)
- Keeps the actual generated code on disk under agent_registry/<name>__<agent_id>/v<n>/
  (deliberately separate from your pipeline's working "generated_agents/" folder)
- Tracks version history so re-generating/iterating on an agent doesn't destroy the old one
- Survives restarts: on startup just call init_db() and everything is there

Drop this file next to your pipeline code (e.g. alongside supervisor.py) and import it
from wherever runtime_check succeeds.
"""

import sqlite3
import shutil
import uuid
import json
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path("agents.db")
# IMPORTANT: this must NOT be the same folder your pipeline writes live agents
# into (settings.generated_agents_dir, typically "generated_agents/"). This is
# a separate, permanent archive — keep it distinct or you'll get the pipeline's
# working copy and the persisted copy tangled together in one folder.
STORAGE_ROOT = Path("agent_registry")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    STORAGE_ROOT.mkdir(exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                display_name TEXT,
                original_prompt TEXT,
                category TEXT,             -- cricket, stocks, weather, news, sports_general, currency, none
                current_version INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',   -- active | archived | failed
                metadata_json TEXT,        -- anything extra: api config, model used, etc.
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_versions (
                agent_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                code_path TEXT NOT NULL,
                prompt_used TEXT,           -- the prompt/instruction that produced this version
                validation_status TEXT,     -- passed | failed
                created_at TEXT,
                PRIMARY KEY (agent_id, version),
                FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_category ON agents(category)")


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def save_agent(
    canonical_name: str,
    display_name: str,
    original_prompt: str,
    category: str,
    source_code_dir: str,
    metadata: dict | None = None,
    validation_status: str = "passed",
) -> str:
    """
    Call this once runtime_check / validator passes for a freshly generated agent.

    source_code_dir: the temp/working folder your pipeline wrote the agent's
    files into (main.py, requirements.txt, .env, etc.) — this gets COPIED into
    permanent storage, so your pipeline's temp dir can be wiped safely after.

    Returns the new agent_id.
    """
    agent_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    dest = STORAGE_ROOT / f"{canonical_name}__{agent_id}" / "v1"
    dest.mkdir(parents=True, exist_ok=True)
    _copy_agent_files(source_code_dir, dest)

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO agents
               (id, canonical_name, display_name, original_prompt, category,
                current_version, status, metadata_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, 'active', ?, ?, ?)""",
            (agent_id, canonical_name, display_name, original_prompt, category,
             json.dumps(metadata or {}), now, now),
        )
        conn.execute(
            """INSERT INTO agent_versions
               (agent_id, version, code_path, prompt_used, validation_status, created_at)
               VALUES (?, 1, ?, ?, ?, ?)""",
            (agent_id, str(dest), original_prompt, validation_status, now),
        )
    return agent_id


def save_new_version(
    agent_id: str,
    source_code_dir: str,
    prompt_used: str,
    validation_status: str = "passed",
) -> int:
    """
    Call this when the user asks to iterate/regenerate an existing agent
    (e.g. 'add caching to this' fed back into your supervisor/coder nodes).

    Returns the new version number.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT current_version, canonical_name FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No agent with id {agent_id}")
        new_version = row["current_version"] + 1
        canonical_name = row["canonical_name"]

    dest = STORAGE_ROOT / f"{canonical_name}__{agent_id}" / f"v{new_version}"
    dest.mkdir(parents=True, exist_ok=True)
    _copy_agent_files(source_code_dir, dest)

    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_versions
               (agent_id, version, code_path, prompt_used, validation_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, new_version, str(dest), prompt_used, validation_status, now),
        )
        conn.execute(
            "UPDATE agents SET current_version = ?, updated_at = ? WHERE id = ?",
            (new_version, now, agent_id),
        )
    return new_version


def get_agent_by_canonical_name(canonical_name: str, status: str = "active") -> dict | None:
    """
    Find an existing agent by its canonical name. Use this before deciding
    whether to call save_agent() (new agent) or save_new_version() (update
    an existing one) — without this check every regeneration creates a
    fresh duplicate row instead of a new version of the same agent.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM agents WHERE canonical_name = ? AND status = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (canonical_name, status),
        ).fetchone()
        if row is None:
            return None
        agent = dict(row)
        agent["metadata"] = json.loads(agent.pop("metadata_json") or "{}")
        return agent


def get_agent(agent_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            return None
        agent = dict(row)
        agent["metadata"] = json.loads(agent.pop("metadata_json") or "{}")
        versions = conn.execute(
            "SELECT version, code_path, prompt_used, validation_status, created_at "
            "FROM agent_versions WHERE agent_id = ? ORDER BY version",
            (agent_id,),
        ).fetchall()
        agent["versions"] = [dict(v) for v in versions]
        return agent


def list_agents(category: str | None = None, status: str = "active") -> list[dict]:
    query = "SELECT * FROM agents WHERE status = ?"
    params = [status]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY updated_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            a = dict(r)
            a["metadata"] = json.loads(a.pop("metadata_json") or "{}")
            out.append(a)
        return out


def get_active_code_path(agent_id: str) -> str | None:
    """Path to the current (latest) version's code folder, ready to run/serve."""
    agent = get_agent(agent_id)
    if not agent or not agent["versions"]:
        return None
    return agent["versions"][-1]["code_path"]


def archive_agent(agent_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE agents SET status = 'archived', updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), agent_id),
        )


def delete_agent(agent_id: str, remove_files: bool = True):
    with get_conn() as conn:
        conn.execute("DELETE FROM agent_versions WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    if remove_files:
        for folder in STORAGE_ROOT.glob(f"*__{agent_id}"):
            shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _copy_agent_files(source_dir: str, dest_dir: Path):
    """Copy generated agent files, skipping junk like __pycache__ and venvs."""
    skip_dirs = {"__pycache__", ".git", "venv", ".venv", "node_modules"}
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel = os.path.relpath(root, source_dir)
        target_root = dest_dir if rel == "." else dest_dir / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), target_root / f)