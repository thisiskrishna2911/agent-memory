from datetime import datetime
from pathlib import Path
from agent_memory import vault, notes_write, sessions


def test_define_project_creates_hub(tmp_path: Path):
    vault.scaffold(tmp_path)
    notes_write.define_project(tmp_path, "alpha")
    assert (tmp_path / "projects" / "alpha" / "_moc.md").exists()
    assert (tmp_path / "sessions" / "alpha").is_dir()


def test_define_project_writes_marker(tmp_path: Path):
    vault.scaffold(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    notes_write.define_project(tmp_path, "alpha", marker_dir=repo)
    assert (repo / ".agentmemory").read_text().strip() == "project: alpha"


def test_write_durable_decision(tmp_path: Path):
    vault.scaffold(tmp_path)
    now = datetime(2026, 6, 10, 14, 30)
    path = notes_write.write_durable(
        tmp_path, type="decision", scope="project", project="alpha",
        title="Use MCP", body="We chose MCP.", links=["architecture"], now=now)
    note = vault.read_note(path)
    assert note.type == "decision"
    assert note.links == ["[[architecture]]"]
    assert "decisions" in str(path)


def test_promote_session_to_decision(tmp_path: Path):
    vault.scaffold(tmp_path)
    spath = sessions.checkpoint(tmp_path, project="alpha", task="Pick DB",
                                summary="Chose Postgres for ACID.",
                                now=datetime(2026, 6, 10, 14, 0))
    rel = str(spath.relative_to(tmp_path))
    dpath = notes_write.promote(tmp_path, rel, as_type="decision",
                                now=datetime(2026, 6, 10, 15, 0))
    note = vault.read_note(dpath)
    assert note.type == "decision"
    assert "Postgres" in note.body
    # Promoted note links back to its origin session.
    assert any("Pick DB" in l or "pick-db" in l for l in note.links)
