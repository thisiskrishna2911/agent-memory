from pathlib import Path
from agent_memory import active


def test_write_then_read_pointer(tmp_path: Path):
    f = tmp_path / "active.json"
    active.write_pointer(f, project="x", project_path="/repo/x",
                         session_note="sessions/x/note.md")
    data = active.read_pointer(f)
    assert data["project"] == "x"
    assert data["project_path"] == "/repo/x"
    assert data["session_note"] == "sessions/x/note.md"


def test_read_missing_pointer_returns_none(tmp_path: Path):
    assert active.read_pointer(tmp_path / "nope.json") is None
