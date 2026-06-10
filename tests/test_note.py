from datetime import datetime
from agent_memory.note import Note, slugify, ts


def test_slugify():
    assert slugify("Use MCP for Memory!") == "use-mcp-for-memory"
    assert slugify("feature/X auth") == "feature-x-auth"


def test_ts_formats_compactly():
    assert ts(datetime(2026, 6, 10, 14, 30)) == "2026-06-10T1430"


def test_note_to_frontmatter_omits_none_project():
    n = Note(type="preference", scope="global", project=None,
             title="Style", body="Tabs", created="2026-06-10T1430",
             updated="2026-06-10T1430")
    meta = n.to_meta()
    assert "project" not in meta
    assert meta["type"] == "preference"
    assert meta["scope"] == "global"


def test_note_includes_project_when_set():
    n = Note(type="session", scope="project", project="feature-x",
             title="T", body="B", created="2026-06-10T1430",
             updated="2026-06-10T1430")
    assert n.to_meta()["project"] == "feature-x"
