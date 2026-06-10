"""The active-session pointer linking the live agent to the snapshot script."""
from __future__ import annotations

import json
from pathlib import Path


def write_pointer(path: Path, project: str, project_path: str,
                  session_note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "project": project,
        "project_path": project_path,
        "session_note": session_note,
    }, indent=2))


def read_pointer(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
