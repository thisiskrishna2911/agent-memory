"""Static configuration for the agent memory system."""
from __future__ import annotations

import os
from pathlib import Path


def vault_root() -> Path:
    """Vault directory; override with AGENT_MEMORY_VAULT (used by tests)."""
    return Path(os.environ.get("AGENT_MEMORY_VAULT",
                               Path.home() / "Documents" / "agentMemory"))


# Subdirectories within the vault root.
GLOBAL_DIR = "global"
PROJECTS_DIR = "projects"
SESSIONS_DIR = "sessions"

# Default number of session snapshots a resume returns.
RESUME_K = 2
# Default mechanical-snapshot interval, in seconds (launchd).
SNAPSHOT_INTERVAL_SECONDS = 600

# Active session pointer file.
ACTIVE_DIR = Path.home() / ".agent-memory"
ACTIVE_FILE = ACTIVE_DIR / "active.json"
