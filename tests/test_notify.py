"""The MCP tools fire a notification on every call (client-agnostic)."""
from pathlib import Path

from agent_memory import notify, server


def test_tool_call_triggers_notification(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_VAULT", str(tmp_path))
    calls: list[str] = []
    monkeypatch.setattr(server, "notify", lambda name: calls.append(name))
    server.memory_list_projects(cwd=str(tmp_path))
    assert calls == ["memory_list_projects"]


def test_notify_disabled_is_silent(monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_NOTIFY", "0")
    notify.notify("memory_test")  # must not raise, must not spawn anything
