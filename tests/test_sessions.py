from datetime import datetime
from pathlib import Path
from agent_memory.note import Note
from agent_memory import vault, sessions


def test_checkpoint_creates_then_updates_same_file(tmp_path: Path):
    vault.scaffold(tmp_path)
    t1 = datetime(2026, 6, 10, 14, 30)
    p1 = sessions.checkpoint(tmp_path, project="x", task="Add login",
                             summary="started", next_steps=["wire form"], now=t1)
    # Same task, later time -> must update the SAME note, not create a new one.
    t2 = datetime(2026, 6, 10, 15, 0)
    p2 = sessions.checkpoint(tmp_path, project="x", task="Add login",
                             summary="form wired", next_steps=["validate"], now=t2)
    assert p1 == p2
    session_files = list((tmp_path / "sessions" / "x").glob("*.md"))
    assert len(session_files) == 1
    note = vault.read_note(p2)
    assert "form wired" in note.body
    assert note.updated == "2026-06-10T1500"


def test_resume_returns_latest_sessions(tmp_path: Path):
    vault.scaffold(tmp_path)
    sessions.checkpoint(tmp_path, project="x", task="Old task",
                        summary="old", now=datetime(2026, 6, 9, 10, 0))
    sessions.checkpoint(tmp_path, project="x", task="New task",
                        summary="new work", now=datetime(2026, 6, 10, 10, 0))
    brief = sessions.resume(tmp_path, project="x", k=1)
    assert len(brief["sessions"]) == 1
    assert brief["sessions"][0]["task"] == "New task"


def test_recent_orders_by_updated(tmp_path: Path):
    vault.scaffold(tmp_path)
    sessions.checkpoint(tmp_path, project="x", task="A",
                        summary="a", now=datetime(2026, 6, 9, 10, 0))
    sessions.checkpoint(tmp_path, project="x", task="B",
                        summary="b", now=datetime(2026, 6, 10, 10, 0))
    items = sessions.recent(tmp_path, project="x", limit=5)
    assert [i["task"] for i in items] == ["B", "A"]
