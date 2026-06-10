from pathlib import Path
from agent_memory.note import Note
from agent_memory import vault


def test_scaffold_creates_structure(tmp_path: Path):
    vault.scaffold(tmp_path)
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "global" / "preferences.md").exists()
    assert (tmp_path / "projects").is_dir()
    assert (tmp_path / "sessions").is_dir()


def test_scaffold_is_idempotent(tmp_path: Path):
    vault.scaffold(tmp_path)
    (tmp_path / "global" / "preferences.md").write_text("MY PREFS")
    vault.scaffold(tmp_path)  # must not overwrite existing content
    assert (tmp_path / "global" / "preferences.md").read_text() == "MY PREFS"


def test_write_then_read_note_roundtrips(tmp_path: Path):
    n = Note(type="decision", scope="project", project="feat-x",
             title="Use MCP", body="We chose MCP.",
             created="2026-06-10T1430", updated="2026-06-10T1430",
             status="resolved", tags=["arch"])
    path = tmp_path / "projects" / "feat-x" / "decisions" / "use-mcp.md"
    vault.write_note(path, n)
    loaded = vault.read_note(path)
    assert loaded.type == "decision"
    assert loaded.project == "feat-x"
    assert loaded.status == "resolved"
    assert loaded.tags == ["arch"]
    assert loaded.body.strip() == "We chose MCP."
    assert loaded.title == "Use MCP"  # derived from body heading or filename
