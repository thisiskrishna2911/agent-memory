"""Ghost-link detection: flag wikilinks whose target note doesn't exist."""
from pathlib import Path

from agent_memory import links, server, vault
from agent_memory.note import Note


def test_find_ghost_links_flags_missing_body_link(tmp_path: Path):
    vault.scaffold(tmp_path)
    vault.write_note(
        tmp_path / "projects" / "x" / "architecture.md",
        Note(type="architecture", scope="project", project="x", title="Arch",
             body="real content", created="2026-06-10T1000", updated="2026-06-10T1000"))
    vault.write_note(
        tmp_path / "projects" / "x" / "decisions" / "d.md",
        Note(type="decision", scope="project", project="x", title="D",
             body="See [[architecture]] and [[ghost-note]].",
             created="2026-06-10T1000", updated="2026-06-10T1000"))
    # 'architecture' resolves; 'ghost-note' does not.
    assert links.find_ghost_links(tmp_path, "projects/x/decisions/d.md") == ["ghost-note"]


def test_find_ghost_links_checks_frontmatter_links(tmp_path: Path):
    vault.scaffold(tmp_path)
    vault.write_note(
        tmp_path / "projects" / "x" / "d.md",
        Note(type="decision", scope="project", project="x", title="D", body="body",
             created="2026-06-10T1000", updated="2026-06-10T1000",
             links=["[[missing-thing]]"]))
    assert links.find_ghost_links(tmp_path, "projects/x/d.md") == ["missing-thing"]


def test_memory_note_reports_ghost_link(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_VAULT", str(tmp_path))
    monkeypatch.setattr(server, "notify", lambda name: None)  # no banners in tests
    r = server.memory_note(type="decision", scope="project", project="x",
                           title="Use X", body="b", links=["nonexistent-note"])
    assert r["ghost_links"] == ["[[nonexistent-note]]"]
    assert "warning" in r


def test_memory_note_clean_when_link_resolves(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_VAULT", str(tmp_path))
    monkeypatch.setattr(server, "notify", lambda name: None)
    server.memory_define_project("x")  # creates projects/x/_moc.md
    r = server.memory_note(type="decision", scope="project", project="x",
                           title="Use Y", body="b", links=["_moc"])
    assert "ghost_links" not in r
