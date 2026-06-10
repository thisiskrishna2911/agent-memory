#!/usr/bin/env python3
"""Append git mechanical state of the active project to its session note.

Run by launchd on a timer and by Claude Code Stop/PreCompact hooks. Safe to run
when no session is active (it just exits).
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.active import read_pointer       # noqa: E402
from agent_memory.config import ACTIVE_FILE, vault_root  # noqa: E402

_MARK = "## Mechanical snapshot"


def _git(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", cwd, *args],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    ptr = read_pointer(ACTIVE_FILE)
    if not ptr:
        return 0
    repo = ptr["project_path"]
    note_path = vault_root() / ptr["session_note"]
    if not note_path.exists():
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    status = _git(repo, "status", "--short") or "(clean)"
    diffstat = _git(repo, "diff", "--stat") or "(no unstaged changes)"

    block = (f"{_MARK}\n_Auto-captured {stamp}_\n\n"
             f"- Branch: `{branch}`\n\n"
             f"```\n{status}\n```\n\n"
             f"<details><summary>diff --stat</summary>\n\n"
             f"```\n{diffstat}\n```\n</details>\n")

    text = note_path.read_text()
    if _MARK in text:
        text = text[:text.index(_MARK)].rstrip() + "\n\n" + block
    else:
        text = text.rstrip() + "\n\n" + block
    note_path.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
