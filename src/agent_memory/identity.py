"""Surface project-identity signals; the agent decides the final slug."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .config import PROJECTS_DIR, SESSIONS_DIR
from .note import slugify


def normalize_remote(url: str) -> str:
    """Normalize a git remote URL to host/owner/repo, lowercased, no .git."""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^ssh://", "", u)
    u = re.sub(r"^git@", "", u)
    u = u.replace(":", "/", 1) if "@" not in u and ":" in u else u
    # git@host:owner/repo -> host/owner/repo (the ':' became '/')
    u = re.sub(r"\.git$", "", u)
    return u


def _git_remote(cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return normalize_remote(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _marker(cwd: Path) -> str | None:
    f = cwd / ".agentmemory"
    if f.exists():
        for line in f.read_text().splitlines():
            if line.strip().startswith("project:"):
                return line.split(":", 1)[1].strip()
    return None


def detect_signals(cwd: Path) -> dict:
    """Return identity signals for the agent to reason over."""
    return {
        "marker": _marker(cwd),
        "git_remote": _git_remote(cwd),
        "folder": slugify(cwd.name),
    }


def list_known_projects(vault_root: Path) -> list[str]:
    """All project slugs already present in the vault (projects/ ∪ sessions/)."""
    names: set[str] = set()
    for sub in (PROJECTS_DIR, SESSIONS_DIR):
        d = vault_root / sub
        if d.is_dir():
            names.update(p.name for p in d.iterdir()
                         if p.is_dir() and not p.name.startswith("."))
    return sorted(names)
