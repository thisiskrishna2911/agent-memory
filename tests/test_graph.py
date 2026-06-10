from pathlib import Path
from agent_memory.note import Note
from agent_memory import vault, graph


def test_extract_links():
    body = "See [[architecture]] and [[decisions/auth|the auth call]]."
    assert graph.extract_links(body) == ["architecture", "decisions/auth"]


def test_traverse_one_hop(tmp_path: Path):
    vault.scaffold(tmp_path)
    vault.write_note(
        tmp_path / "projects" / "x" / "_moc.md",
        Note(type="architecture", scope="project", project="x", title="MOC",
             body="Hub. [[architecture]]",
             created="2026-06-10T1000", updated="2026-06-10T1000"))
    vault.write_note(
        tmp_path / "projects" / "x" / "architecture.md",
        Note(type="architecture", scope="project", project="x", title="Arch",
             body="Details here.",
             created="2026-06-10T1000", updated="2026-06-10T1000"))
    neighbors = graph.traverse(tmp_path, "projects/x/_moc.md", depth=1)
    titles = {n["title"] for n in neighbors}
    assert "Arch" in titles
