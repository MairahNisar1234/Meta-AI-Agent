"""
persistence.py

Drop-in persistence layer for the meta-agent system — MongoDB edition.

What it does:
- Stores metadata about every generated agent in MongoDB (db: meta_agents, collection: agents)
- Keeps the actual generated code on disk under agent_registry/<name>__<agent_id>/v<n>/
  (deliberately separate from your pipeline's working "generated_agents/" folder)
- Tracks version history (embedded as an array on the agent document) so
  re-generating/iterating on an agent doesn't destroy the old one
- Survives restarts: on startup just call init_db() and everything is there

Drop this file next to your pipeline code (e.g. alongside supervisor.py) and import it
from wherever runtime_check succeeds.

Requires: pip install pymongo
Configure connection via the MONGO_URI env var (defaults to a local instance).
"""

import shutil
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient, ReturnDocument

MONGO_URI = os.environ.get("MONGO_URI", "https://meta-ai-agent-uwbi.onrender.com")
DB_NAME = os.environ.get("META_AGENT_DB_NAME", "meta_agents")

# IMPORTANT: this must NOT be the same folder your pipeline writes live agents
# into (settings.generated_agents_dir, typically "generated_agents/"). This is
# a separate, permanent archive — keep it distinct or you'll get the pipeline's
# working copy and the persisted copy tangled together in one folder.
STORAGE_ROOT = Path("agent_registry")

_client: MongoClient | None = None


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db():
    return get_client()[DB_NAME]


def _agents_collection():
    return get_db()["agents"]


def init_db():
    """Create the storage folder and required indexes. Safe to call repeatedly."""
    STORAGE_ROOT.mkdir(exist_ok=True)
    col = _agents_collection()
    # _id is used as the agent_id (string), so no separate id index needed.
    col.create_index("canonical_name")
    col.create_index("category")
    col.create_index("status")
    col.create_index([("canonical_name", 1), ("status", 1), ("updated_at", -1)])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    now = _now()
    dest = STORAGE_ROOT / f"{canonical_name}__{agent_id}" / "v1"
    dest.mkdir(parents=True, exist_ok=True)
    _copy_agent_files(source_code_dir, dest)

    doc = {
        "_id": agent_id,
        "canonical_name": canonical_name,
        "display_name": display_name,
        "original_prompt": original_prompt,
        "category": category,
        "current_version": 1,
        "status": "active",
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
        "versions": [
            {
                "version": 1,
                "code_path": str(dest),
                "prompt_used": original_prompt,
                "validation_status": validation_status,
                "created_at": now,
            }
        ],
    }
    _agents_collection().insert_one(doc)
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
    col = _agents_collection()
    row = col.find_one({"_id": agent_id}, {"current_version": 1, "canonical_name": 1})
    if row is None:
        raise ValueError(f"No agent with id {agent_id}")

    new_version = row["current_version"] + 1
    canonical_name = row["canonical_name"]

    dest = STORAGE_ROOT / f"{canonical_name}__{agent_id}" / f"v{new_version}"
    dest.mkdir(parents=True, exist_ok=True)
    _copy_agent_files(source_code_dir, dest)

    now = _now()
    version_entry = {
        "version": new_version,
        "code_path": str(dest),
        "prompt_used": prompt_used,
        "validation_status": validation_status,
        "created_at": now,
    }
    col.update_one(
        {"_id": agent_id},
        {
            "$push": {"versions": version_entry},
            "$set": {"current_version": new_version, "updated_at": now},
        },
    )
    return new_version


def get_agent_by_canonical_name(canonical_name: str, status: str = "active") -> dict | None:
    """
    Find an existing agent by its canonical name. Use this before deciding
    whether to call save_agent() (new agent) or save_new_version() (update
    an existing one) — without this check every regeneration creates a
    fresh duplicate row instead of a new version of the same agent.
    """
    doc = _agents_collection().find_one(
        {"canonical_name": canonical_name, "status": status},
        sort=[("updated_at", -1)],
    )
    return _with_id(doc)


def get_agent(agent_id: str) -> dict | None:
    doc = _agents_collection().find_one({"_id": agent_id})
    return _with_id(doc)


def list_agents(category: str | None = None, status: str = "active") -> list[dict]:
    query = {"status": status}
    if category:
        query["category"] = category
    cursor = _agents_collection().find(query).sort("updated_at", -1)
    return [_with_id(doc) for doc in cursor]


def get_active_code_path(agent_id: str) -> str | None:
    """Path to the current (latest) version's code folder, ready to run/serve."""
    agent = get_agent(agent_id)
    if not agent or not agent["versions"]:
        return None
    return agent["versions"][-1]["code_path"]


def archive_agent(agent_id: str):
    _agents_collection().update_one(
        {"_id": agent_id},
        {"$set": {"status": "archived", "updated_at": _now()}},
    )


def delete_agent(agent_id: str, remove_files: bool = True):
    _agents_collection().delete_one({"_id": agent_id})
    if remove_files:
        for folder in STORAGE_ROOT.glob(f"*__{agent_id}"):
            shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _with_id(doc: dict | None) -> dict | None:
    """Rename Mongo's `_id` to `id` so callers see the same shape as before."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


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