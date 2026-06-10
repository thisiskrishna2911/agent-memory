"""Best-effort desktop notifications when memory tools are invoked.

Lives in the server (not a Claude hook) so it fires for ANY MCP client that
calls a tool. Never raises and never blocks the tool call: a notification
failure must not break memory.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

_TITLE = "agent-memory MCP"


def _enabled() -> bool:
    # Opt-out kill switch for when the notifications get noisy.
    return os.environ.get("AGENT_MEMORY_NOTIFY", "1").lower() in ("1", "true", "yes")


def notify(tool: str) -> None:
    """Fire a non-blocking macOS notification that `tool` was called.

    Silently no-ops off macOS, when osascript is missing, or when disabled via
    AGENT_MEMORY_NOTIFY=0. Tool names are fixed identifiers (`memory_*`), so the
    AppleScript string needs no escaping.
    """
    if not _enabled() or sys.platform != "darwin":
        return
    osa = shutil.which("osascript")
    if not osa:
        return
    script = f'display notification "{tool}" with title "{_TITLE}"'
    try:
        subprocess.Popen([osa, "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
