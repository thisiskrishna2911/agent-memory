from pathlib import Path
from agent_memory.note import Note
from agent_memory import vault, search


def _seed(tmp_path: Path):
    vault.scaffold(tmp_path)
    vault.write_note(
        tmp_path / "projects" / "x" / "decisions" / "auth.md",
        Note(type="decision", scope="project", project="x", title="Auth tokens",
             body="Use httpOnly cookies for auth tokens.",
             created="2026-06-10T1000", updated="2026-06-10T1000", tags=["auth"]))
    vault.write_note(
        tmp_path / "projects" / "x" / "architecture.md",
        Note(type="architecture", scope="project", project="x", title="Arch",
             body="The service uses a worker queue.",
             created="2026-06-09T1000", updated="2026-06-09T1000"))


def test_search_matches_body(tmp_path: Path):
    _seed(tmp_path)
    hits = search.search(tmp_path, "cookies")
    assert len(hits) == 1
    assert hits[0]["title"] == "Auth tokens"
    assert "cookies" in hits[0]["snippet"].lower()


def test_search_filters_by_type(tmp_path: Path):
    _seed(tmp_path)
    hits = search.search(tmp_path, "service", type="decision")
    assert hits == []  # 'service' is in the architecture note, not a decision


def test_search_filters_by_project(tmp_path: Path):
    _seed(tmp_path)
    hits = search.search(tmp_path, "queue", project="x")
    assert len(hits) == 1
    assert hits[0]["title"] == "Arch"


def test_search_respects_limit(tmp_path: Path):
    _seed(tmp_path)
    hits = search.search(tmp_path, "the", limit=1)
    assert len(hits) == 1
