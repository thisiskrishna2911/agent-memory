# Agent Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MCP server, backed by the Obsidian vault at `~/Documents/agentMemory`, that gives Claude resumable working context and a durable knowledge graph, with automatic checkpoint triggers so an abrupt power-off never loses hours of work.

**Architecture:** A pure-Python core library (`src/agent_memory/`) holds all logic — frontmatter, vault IO, project identity, search, graph traversal, sessions, durable notes — and is unit-tested in isolation. A thin MCP server (`server.py`) wires that core to 10 MCP tools. Durability comes from two complementary mechanisms: **semantic checkpoints** the agent writes via the `memory_checkpoint` tool (immediately persisted to disk), and **mechanical snapshots** a standalone script writes (git state + changed files of the active project) driven by a launchd timer and Claude Code `Stop`/`PreCompact` hooks. An "active session pointer" (`~/.agent-memory/active.json`) connects the two so the mechanical script knows which project to snapshot.

**Tech Stack:** Python 3.13, `uv` for project/deps, the official `mcp` SDK, `PyYAML` for frontmatter, `pytest` for tests, macOS `launchd` for the timer. No network, no embeddings, no local LLM in v1 (reserved for v2/v3 per the spec).

**Spec:** `docs/superpowers/specs/2026-06-10-agent-memory-system-design.md`

---

## Conventions used in this plan

- All timestamp-producing functions take an optional `now: datetime | None` parameter (defaulting to `datetime.now()`) so tests pass a fixed time and stay deterministic.
- Tests use `pytest`'s `tmp_path` fixture to build a throwaway vault — no test touches the real `~/Documents/agentMemory`.
- `VAULT` is configurable via the `AGENT_MEMORY_VAULT` env var (defaults to `~/Documents/agentMemory`) so tests and the server can point elsewhere.
- Run every command from the repo root: `~/Desktop/agent-memory`.

## File Structure

```
agent-memory/
├── pyproject.toml                         # uv project + deps + pytest config
├── src/agent_memory/
│   ├── __init__.py
│   ├── config.py                          # VAULT path, constants
│   ├── frontmatter.py                     # parse/serialize YAML frontmatter + body
│   ├── note.py                            # Note dataclass + slugify + title
│   ├── vault.py                           # scaffold dirs, read_note, write_note
│   ├── identity.py                        # project signals, known projects, normalize remote
│   ├── search.py                          # full-text + frontmatter-filter search
│   ├── graph.py                           # wikilink extraction + traverse
│   ├── sessions.py                        # checkpoint (idempotent), resume, recent
│   ├── notes_write.py                     # write_durable, promote, define_project
│   ├── active.py                          # read/write ~/.agent-memory/active.json
│   └── server.py                          # MCP server: 10 tools wired to core
├── scripts/
│   └── mechanical_snapshot.py             # git/file snapshot of active project
├── launchd/
│   └── com.krishna.agentmemory.snapshot.plist
├── tests/
│   ├── test_frontmatter.py
│   ├── test_note.py
│   ├── test_vault.py
│   ├── test_identity.py
│   ├── test_search.py
│   ├── test_graph.py
│   ├── test_sessions.py
│   ├── test_notes_write.py
│   └── test_active.py
└── .claude/
    ├── settings.json                      # add Stop/PreCompact hooks
    └── skills/agent-memory/
        ├── SKILL.md                       # the memory protocol for any agent
        └── README.md                      # install + copy instructions
```

---

## Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`, `src/agent_memory/__init__.py`, `tests/__init__.py`, `.gitignore` (append)

- [ ] **Step 1: Create the feature branch**

Run:
```bash
cd ~/Desktop/agent-memory && git checkout -b feature/agent-memory-system
```

- [ ] **Step 2: Initialize the uv project and add deps**

Run:
```bash
cd ~/Desktop/agent-memory
uv init --bare --python 3.13
uv add "mcp[cli]" pyyaml
uv add --dev pytest
```

- [ ] **Step 3: Create `pyproject.toml` pytest config**

Append to the generated `pyproject.toml` (keep existing `[project]`/dependency sections uv created):

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_memory"]
```

- [ ] **Step 4: Create package + test init files**

```bash
mkdir -p src/agent_memory tests scripts launchd .claude/skills/agent-memory
touch src/agent_memory/__init__.py tests/__init__.py
```

- [ ] **Step 5: Ignore vault test artifacts and venv**

Append to `.gitignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 6: Verify pytest runs (no tests yet)**

Run: `uv run pytest -q`
Expected: `no tests ran` (exit 0 or 5), no import errors.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: scaffold agent-memory uv project"
```

---

## Task 1: Frontmatter parse/serialize

**Files:**
- Create: `src/agent_memory/frontmatter.py`
- Test: `tests/test_frontmatter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_frontmatter.py
from agent_memory.frontmatter import parse, serialize


def test_parse_splits_meta_and_body():
    text = "---\ntype: session\ntags:\n  - a\n  - b\n---\n\nHello body\n"
    meta, body = parse(text)
    assert meta["type"] == "session"
    assert meta["tags"] == ["a", "b"]
    assert body.strip() == "Hello body"


def test_parse_no_frontmatter_returns_empty_meta():
    meta, body = parse("just text, no frontmatter")
    assert meta == {}
    assert body == "just text, no frontmatter"


def test_serialize_roundtrips():
    meta = {"type": "decision", "scope": "project", "tags": ["x"]}
    text = serialize(meta, "Body here")
    meta2, body2 = parse(text)
    assert meta2["type"] == "decision"
    assert meta2["scope"] == "project"
    assert meta2["tags"] == ["x"]
    assert body2.strip() == "Body here"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_frontmatter.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.frontmatter'`

- [ ] **Step 3: Implement `frontmatter.py`**

```python
# src/agent_memory/frontmatter.py
"""Parse and serialize Obsidian-style YAML frontmatter + Markdown body."""
from __future__ import annotations

import yaml

_DELIM = "---"


def parse(text: str) -> tuple[dict, str]:
    """Return (meta, body). If no frontmatter block, meta is {} and body is text."""
    if not text.startswith(_DELIM):
        return {}, text
    parts = text.split(_DELIM, 2)
    # parts == ["", "<yaml>", "<body>"] for a well-formed document
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        return {}, text
    return meta, parts[2].lstrip("\n")


def serialize(meta: dict, body: str) -> str:
    """Render meta as a YAML frontmatter block followed by body."""
    yaml_block = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"{_DELIM}\n{yaml_block}\n{_DELIM}\n\n{body.strip()}\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_frontmatter.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/frontmatter.py tests/test_frontmatter.py
git commit -m "feat: frontmatter parse/serialize"
```

---

## Task 2: Config + Note model

**Files:**
- Create: `src/agent_memory/config.py`, `src/agent_memory/note.py`
- Test: `tests/test_note.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_note.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_note.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.note'`

- [ ] **Step 3: Implement `config.py`**

```python
# src/agent_memory/config.py
"""Static configuration for the agent memory system."""
from __future__ import annotations

import os
from pathlib import Path


def vault_root() -> Path:
    """Vault directory; override with AGENT_MEMORY_VAULT (used by tests)."""
    return Path(os.environ.get("AGENT_MEMORY_VAULT",
                               Path.home() / "Documents" / "agentMemory"))


# Subdirectories within the vault root.
GLOBAL_DIR = "global"
PROJECTS_DIR = "projects"
SESSIONS_DIR = "sessions"

# Default number of session snapshots a resume returns.
RESUME_K = 2
# Default mechanical-snapshot interval, in seconds (launchd).
SNAPSHOT_INTERVAL_SECONDS = 600

# Active session pointer file.
ACTIVE_DIR = Path.home() / ".agent-memory"
ACTIVE_FILE = ACTIVE_DIR / "active.json"
```

- [ ] **Step 4: Implement `note.py`**

```python
# src/agent_memory/note.py
"""The Note model plus slug/timestamp helpers shared across the core."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


def slugify(text: str) -> str:
    """Lowercase, replace non-alphanumerics with hyphens, collapse repeats."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return s.strip("-")


def ts(now: datetime | None = None) -> str:
    """Compact sortable timestamp, e.g. 2026-06-10T1430."""
    now = now or datetime.now()
    return now.strftime("%Y-%m-%dT%H%M")


@dataclass
class Note:
    type: str                       # session|decision|architecture|convention|preference|glossary
    scope: str                      # global|project
    title: str
    body: str
    created: str
    updated: str
    project: str | None = None
    status: str | None = None       # active|resolved|superseded
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    def to_meta(self) -> dict:
        """Frontmatter dict, omitting empty optional keys for clean notes."""
        meta: dict = {"type": self.type, "scope": self.scope}
        if self.project:
            meta["project"] = self.project
        if self.status:
            meta["status"] = self.status
        meta["created"] = self.created
        meta["updated"] = self.updated
        if self.tags:
            meta["tags"] = self.tags
        if self.links:
            meta["links"] = self.links
        return meta
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_note.py -q`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/agent_memory/config.py src/agent_memory/note.py tests/test_note.py
git commit -m "feat: config + Note model"
```

---

## Task 3: Vault scaffold + read/write

**Files:**
- Create: `src/agent_memory/vault.py`
- Test: `tests/test_vault.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vault.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vault.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.vault'`

- [ ] **Step 3: Implement `vault.py`**

```python
# src/agent_memory/vault.py
"""Vault scaffolding and Note <-> file IO."""
from __future__ import annotations

from pathlib import Path

from .config import GLOBAL_DIR, PROJECTS_DIR, SESSIONS_DIR
from .frontmatter import parse, serialize
from .note import Note

# Seed files created once at scaffold time; never overwritten if present.
_SEED = {
    "index.md": "# Agent Memory — Index\n\nRoot map of content. "
                "Entry point for graph traversal.\n\n- [[global/preferences]]\n",
    f"{GLOBAL_DIR}/preferences.md": "---\ntype: preference\nscope: global\n---\n\n"
                                    "# Preferences\n\nHow I like to work.\n",
    f"{GLOBAL_DIR}/conventions.md": "---\ntype: convention\nscope: global\n---\n\n"
                                    "# Global Conventions\n",
    f"{GLOBAL_DIR}/people-glossary.md": "---\ntype: glossary\nscope: global\n---\n\n"
                                        "# People & Terms\n",
}


def scaffold(root: Path) -> None:
    """Create the vault directory tree and seed files. Idempotent."""
    (root / GLOBAL_DIR).mkdir(parents=True, exist_ok=True)
    (root / PROJECTS_DIR).mkdir(parents=True, exist_ok=True)
    (root / SESSIONS_DIR).mkdir(parents=True, exist_ok=True)
    for rel, content in _SEED.items():
        path = root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


def _title_from(body: str, path: Path) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def write_note(path: Path, note: Note) -> None:
    """Serialize a Note to disk, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize(note.to_meta(), note.body))


def read_note(path: Path) -> Note:
    """Load a Note from disk. Title derived from first heading or filename."""
    meta, body = parse(path.read_text())
    return Note(
        type=meta.get("type", "note"),
        scope=meta.get("scope", "global"),
        project=meta.get("project"),
        status=meta.get("status"),
        title=_title_from(body, path),
        body=body,
        created=meta.get("created", ""),
        updated=meta.get("updated", ""),
        tags=meta.get("tags", []) or [],
        links=meta.get("links", []) or [],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vault.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/vault.py tests/test_vault.py
git commit -m "feat: vault scaffold + note IO"
```

---

## Task 4: Project identity signals

**Files:**
- Create: `src/agent_memory/identity.py`
- Test: `tests/test_identity.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_identity.py
from pathlib import Path
from agent_memory import identity, vault


def test_normalize_remote_strips_protocol_and_git():
    assert identity.normalize_remote(
        "git@github.com:krishna/feat-x.git") == "github.com/krishna/feat-x"
    assert identity.normalize_remote(
        "https://github.com/Krishna/Feat-X.git") == "github.com/krishna/feat-x"


def test_marker_signal_read(tmp_path: Path):
    (tmp_path / ".agentmemory").write_text("project: my-proj\n")
    sig = identity.detect_signals(tmp_path)
    assert sig["marker"] == "my-proj"


def test_folder_signal_fallback(tmp_path: Path):
    proj = tmp_path / "Some Cool Repo"
    proj.mkdir()
    sig = identity.detect_signals(proj)
    assert sig["folder"] == "some-cool-repo"
    assert sig["marker"] is None


def test_list_known_projects(tmp_path: Path):
    vault.scaffold(tmp_path)
    (tmp_path / "projects" / "alpha").mkdir(parents=True)
    (tmp_path / "sessions" / "beta").mkdir(parents=True)
    known = identity.list_known_projects(tmp_path)
    assert known == ["alpha", "beta"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_identity.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.identity'`

- [ ] **Step 3: Implement `identity.py`**

```python
# src/agent_memory/identity.py
"""Surface project-identity signals; the agent decides the final slug."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .config import PROJECTS_DIR, SESSIONS_DIR
from .note import slugify


def normalize_remote(url: str) -> str:
    """Normalize a git remote URL to host/owner/repo, lowercased, no .git."""
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^git@", "", u)
    u = u.replace(":", "/", 1) if "@" not in u and ":" in u else u
    # git@host:owner/repo -> host/owner/repo (the ':' became '/')
    u = re.sub(r"\.git$", "", u)
    return u


def _git_remote(cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return normalize_remote(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _marker(cwd: Path) -> str | None:
    f = cwd / ".agentmemory"
    if f.exists():
        for line in f.read_text().splitlines():
            if line.strip().startswith("project:"):
                return line.split(":", 1)[1].strip()
    return None


def detect_signals(cwd: Path) -> dict:
    """Return identity signals for the agent to reason over."""
    return {
        "marker": _marker(cwd),
        "git_remote": _git_remote(cwd),
        "folder": slugify(cwd.name),
    }


def list_known_projects(vault_root: Path) -> list[str]:
    """All project slugs already present in the vault (projects/ ∪ sessions/)."""
    names: set[str] = set()
    for sub in (PROJECTS_DIR, SESSIONS_DIR):
        d = vault_root / sub
        if d.is_dir():
            names.update(p.name for p in d.iterdir()
                         if p.is_dir() and not p.name.startswith("."))
    return sorted(names)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_identity.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/identity.py tests/test_identity.py
git commit -m "feat: project identity signals"
```

---

## Task 5: Search (full-text + frontmatter filter)

**Files:**
- Create: `src/agent_memory/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_search.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_search.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.search'`

- [ ] **Step 3: Implement `search.py`**

```python
# src/agent_memory/search.py
"""In-process full-text + frontmatter-filter search over the vault."""
from __future__ import annotations

from pathlib import Path

from .vault import read_note


def _snippet(body: str, query: str, width: int = 120) -> str:
    low = body.lower()
    i = low.find(query.lower())
    if i == -1:
        return body.strip()[:width]
    start = max(0, i - width // 2)
    return body[start:start + width].strip().replace("\n", " ")


def search(vault_root: Path, query: str, scope: str | None = None,
           project: str | None = None, type: str | None = None,
           limit: int = 10) -> list[dict]:
    """Rank notes by query-term frequency in title+body, after filtering.

    Returns dicts: {title, path, snippet, tags, type}.
    """
    q = query.lower()
    hits: list[tuple[int, dict]] = []
    for md in sorted(vault_root.rglob("*.md")):
        if ".obsidian" in md.parts:
            continue
        note = read_note(md)
        if scope and note.scope != scope:
            continue
        if project and note.project != project:
            continue
        if type and note.type != type:
            continue
        haystack = f"{note.title}\n{note.body}".lower()
        score = haystack.count(q)
        if score == 0:
            continue
        hits.append((score, {
            "title": note.title,
            "path": str(md.relative_to(vault_root)),
            "snippet": _snippet(note.body, query),
            "tags": note.tags,
            "type": note.type,
        }))
    hits.sort(key=lambda h: h[0], reverse=True)
    return [h[1] for h in hits[:limit]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_search.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/search.py tests/test_search.py
git commit -m "feat: full-text + filtered search"
```

---

## Task 6: Graph traversal (wikilinks)

**Files:**
- Create: `src/agent_memory/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_graph.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.graph'`

- [ ] **Step 3: Implement `graph.py`**

```python
# src/agent_memory/graph.py
"""Wikilink extraction and breadth-limited graph traversal."""
from __future__ import annotations

import re
from pathlib import Path

from .vault import read_note

_LINK = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]+)?\]\]")


def extract_links(body: str) -> list[str]:
    """Return wikilink targets (without display alias), in order, de-duped."""
    seen: list[str] = []
    for m in _LINK.finditer(body):
        target = m.group(1).strip()
        if target not in seen:
            seen.append(target)
    return seen


def _resolve(vault_root: Path, target: str) -> Path | None:
    """Resolve a wikilink target to a file: exact path, else by basename."""
    direct = vault_root / (target if target.endswith(".md") else f"{target}.md")
    if direct.exists():
        return direct
    base = target.split("/")[-1]
    for md in vault_root.rglob(f"{base}.md"):
        if ".obsidian" not in md.parts:
            return md
    return None


def traverse(vault_root: Path, rel_path: str, depth: int = 1) -> list[dict]:
    """Return neighbor notes reachable within `depth` hops of rel_path."""
    start = vault_root / rel_path
    visited: set[Path] = {start}
    frontier = [start]
    out: list[dict] = []
    for _ in range(depth):
        nxt: list[Path] = []
        for path in frontier:
            if not path.exists():
                continue
            note = read_note(path)
            for target in extract_links(note.body):
                resolved = _resolve(vault_root, target)
                if resolved and resolved not in visited:
                    visited.add(resolved)
                    nxt.append(resolved)
                    n = read_note(resolved)
                    out.append({
                        "title": n.title,
                        "path": str(resolved.relative_to(vault_root)),
                        "snippet": n.body.strip()[:120].replace("\n", " "),
                        "type": n.type,
                    })
        frontier = nxt
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_graph.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/graph.py tests/test_graph.py
git commit -m "feat: wikilink graph traversal"
```

---

## Task 7: Sessions — checkpoint, resume, recent

**Files:**
- Create: `src/agent_memory/sessions.py`
- Test: `tests/test_sessions.py`

**Idempotency rule:** a checkpoint for a `(project, task)` updates the existing
*active* session note for that task instead of creating a new file. We find it by
scanning `sessions/<project>/` for a note whose `status == "active"` and whose
filename ends with the task slug.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sessions.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sessions.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.sessions'`

- [ ] **Step 3: Implement `sessions.py`**

```python
# src/agent_memory/sessions.py
"""Working-context session snapshots: checkpoint (idempotent), resume, recent."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import SESSIONS_DIR
from .note import Note, slugify, ts
from .vault import read_note, write_note


def _session_dir(vault_root: Path, project: str) -> Path:
    return vault_root / SESSIONS_DIR / project


def _render_body(task: str, summary: str, files, next_steps,
                 open_questions, prev_link: str | None) -> str:
    lines = [f"# {task}", "", "## Summary", summary, ""]
    if files:
        lines += ["## Files touched", *[f"- `{f}`" for f in files], ""]
    if next_steps:
        lines += ["## Next steps", *[f"- [ ] {s}" for s in next_steps], ""]
    if open_questions:
        lines += ["## Open questions", *[f"- {q}" for q in open_questions], ""]
    if prev_link:
        lines += [f"Previous: [[{prev_link}]]", ""]
    return "\n".join(lines)


def _find_active(vault_root: Path, project: str, task_slug: str) -> Path | None:
    d = _session_dir(vault_root, project)
    if not d.is_dir():
        return None
    for md in d.glob("*.md"):
        if md.stem.endswith(task_slug) and read_note(md).status == "active":
            return md
    return None


def checkpoint(vault_root: Path, project: str, task: str, summary: str,
               files: list[str] | None = None,
               next_steps: list[str] | None = None,
               open_questions: list[str] | None = None,
               now: datetime | None = None) -> Path:
    """Create or update the active session snapshot for (project, task)."""
    now = now or datetime.now()
    task_slug = slugify(task)
    existing = _find_active(vault_root, project, task_slug)
    body = _render_body(task, summary, files, next_steps, open_questions, None)

    if existing is not None:
        note = read_note(existing)
        note.body = body
        note.updated = ts(now)
        write_note(existing, note)
        return existing

    path = _session_dir(vault_root, project) / f"{ts(now)}-{task_slug}.md"
    note = Note(type="session", scope="project", project=project, status="active",
                title=task, body=body, created=ts(now), updated=ts(now),
                tags=[task_slug])
    write_note(path, note)
    return path


def _session_summaries(vault_root: Path, project: str) -> list[dict]:
    d = _session_dir(vault_root, project)
    if not d.is_dir():
        return []
    items = []
    for md in d.glob("*.md"):
        n = read_note(md)
        items.append({"task": n.title, "path": str(md.relative_to(vault_root)),
                      "updated": n.updated, "status": n.status,
                      "body": n.body})
    items.sort(key=lambda i: i["updated"], reverse=True)
    return items


def recent(vault_root: Path, project: str, limit: int = 5) -> list[dict]:
    return [{k: v for k, v in i.items() if k != "body"}
            for i in _session_summaries(vault_root, project)[:limit]]


def resume(vault_root: Path, project: str, k: int = 2) -> dict:
    """Bounded brief: latest k sessions (full body) for one-shot rehydration."""
    sessions = _session_summaries(vault_root, project)[:k]
    return {"project": project, "sessions": sessions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sessions.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/sessions.py tests/test_sessions.py
git commit -m "feat: session checkpoint/resume/recent"
```

---

## Task 8: Durable notes — write, promote, define_project

**Files:**
- Create: `src/agent_memory/notes_write.py`
- Test: `tests/test_notes_write.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_notes_write.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_notes_write.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.notes_write'`

- [ ] **Step 3: Implement `notes_write.py`**

```python
# src/agent_memory/notes_write.py
"""Durable-note writes: define_project, write_durable, promote."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import PROJECTS_DIR, SESSIONS_DIR
from .note import Note, slugify, ts
from .vault import read_note, write_note

# Durable note type -> subpath under projects/<project>/ (file or dir).
_TYPE_LOCATION = {
    "decision": "decisions",          # one file per decision inside this dir
    "architecture": "architecture",   # single file
    "convention": "conventions",      # single file
    "glossary": "glossary",           # single file
}


def define_project(vault_root: Path, slug: str,
                   marker_dir: Path | None = None) -> Path:
    """Register a project: create its hub note + sessions dir; optional marker."""
    moc = vault_root / PROJECTS_DIR / slug / "_moc.md"
    if not moc.exists():
        write_note(moc, Note(
            type="architecture", scope="project", project=slug,
            title=f"{slug} — Map of Content",
            body=f"# {slug} — Map of Content\n\nHub note for `{slug}`.\n",
            created=ts(), updated=ts()))
    (vault_root / SESSIONS_DIR / slug).mkdir(parents=True, exist_ok=True)
    if marker_dir is not None:
        (marker_dir / ".agentmemory").write_text(f"project: {slug}\n")
    return moc


def _as_links(links: list[str] | None) -> list[str]:
    out = []
    for l in links or []:
        out.append(l if l.startswith("[[") else f"[[{l}]]")
    return out


def write_durable(vault_root: Path, type: str, scope: str, title: str,
                  body: str, project: str | None = None,
                  links: list[str] | None = None,
                  now: datetime | None = None) -> Path:
    """Write a durable note to its conventional location."""
    now = now or datetime.now()
    note = Note(type=type, scope=scope, project=project, title=title,
                body=body if body.startswith("#") else f"# {title}\n\n{body}",
                created=ts(now), updated=ts(now), links=_as_links(links))
    if scope == "global":
        path = vault_root / "global" / f"{slugify(title)}.md"
    else:
        loc = _TYPE_LOCATION.get(type, "notes")
        base = vault_root / PROJECTS_DIR / project / loc
        # 'decisions' is a directory of dated notes; others are single files.
        if loc == "decisions":
            path = base / f"{now.strftime('%Y-%m-%d')}-{slugify(title)}.md"
        else:
            path = base.with_suffix(".md")
    write_note(path, note)
    return path


def promote(vault_root: Path, session_rel_path: str, as_type: str,
            now: datetime | None = None) -> Path:
    """Turn a session insight into a durable note linking back to its origin."""
    now = now or datetime.now()
    session = read_note(vault_root / session_rel_path)
    back = f"[[{Path(session_rel_path).stem}]]"
    return write_durable(
        vault_root, type=as_type, scope=session.scope, project=session.project,
        title=session.title, body=session.body,
        links=[back], now=now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_notes_write.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/notes_write.py tests/test_notes_write.py
git commit -m "feat: durable notes, promote, define_project"
```

---

## Task 9: Active session pointer

**Files:**
- Create: `src/agent_memory/active.py`
- Test: `tests/test_active.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_active.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_active.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent_memory.active'`

- [ ] **Step 3: Implement `active.py`**

```python
# src/agent_memory/active.py
"""The active-session pointer linking the live agent to the snapshot script."""
from __future__ import annotations

import json
from pathlib import Path


def write_pointer(path: Path, project: str, project_path: str,
                  session_note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "project": project,
        "project_path": project_path,
        "session_note": session_note,
    }, indent=2))


def read_pointer(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_active.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/active.py tests/test_active.py
git commit -m "feat: active session pointer"
```

---

## Task 10: MCP server wiring

**Files:**
- Create: `src/agent_memory/server.py`

No new unit tests here (logic is already tested); we verify by running the server
and listing tools. The server is a thin adapter: every tool calls a core function.

- [ ] **Step 1: Implement `server.py`**

```python
# src/agent_memory/server.py
"""MCP server exposing 10 memory tools backed by the tested core library."""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import graph, identity, notes_write, search, sessions, vault
from .active import write_pointer
from .config import ACTIVE_FILE, RESUME_K, vault_root

mcp = FastMCP("agent-memory")


def _root() -> Path:
    root = vault_root()
    vault.scaffold(root)  # ensure structure exists on first use
    return root


@mcp.tool()
def memory_list_projects(cwd: str = ".") -> dict:
    """List known project slugs and identity signals for the current folder.

    Call at session start; if the active project is ambiguous or new, ASK the
    user which project this is before resuming.
    """
    root = _root()
    return {
        "known": identity.list_known_projects(root),
        "signals": identity.detect_signals(Path(cwd).expanduser().resolve()),
    }


@mcp.tool()
def memory_search(query: str, scope: str | None = None,
                  project: str | None = None, type: str | None = None,
                  limit: int = 10) -> list[dict]:
    """Search memory by text; returns title+snippet hits (not full bodies)."""
    return search.search(_root(), query, scope=scope, project=project,
                         type=type, limit=limit)


@mcp.tool()
def memory_read(path: str) -> dict:
    """Read one full note by its vault-relative path."""
    note = vault.read_note(_root() / path)
    return {"title": note.title, "type": note.type, "body": note.body,
            "tags": note.tags, "links": note.links, "updated": note.updated}


@mcp.tool()
def memory_traverse(path: str, depth: int = 1) -> list[dict]:
    """Return notes linked from `path` within `depth` hops (snippets only)."""
    return graph.traverse(_root(), path, depth=depth)


@mcp.tool()
def memory_recent(project: str, limit: int = 5) -> list[dict]:
    """Recent sessions for a project, newest first."""
    return sessions.recent(_root(), project, limit=limit)


@mcp.tool()
def memory_resume(project: str, cwd: str = ".") -> dict:
    """One-shot rehydrate: the latest session snapshots for a project.

    Updates the active-session pointer so the mechanical snapshot script knows
    which project to protect.
    """
    root = _root()
    brief = sessions.resume(root, project, k=RESUME_K)
    if brief["sessions"]:
        write_pointer(ACTIVE_FILE, project=project,
                      project_path=str(Path(cwd).expanduser().resolve()),
                      session_note=brief["sessions"][0]["path"])
    return brief


@mcp.tool()
def memory_checkpoint(project: str, task: str, summary: str,
                      files: list[str] | None = None,
                      next_steps: list[str] | None = None,
                      open_questions: list[str] | None = None,
                      cwd: str = ".") -> dict:
    """Save/update the active working-context snapshot for (project, task)."""
    root = _root()
    path = sessions.checkpoint(root, project, task, summary, files=files,
                               next_steps=next_steps, open_questions=open_questions)
    rel = str(path.relative_to(root))
    write_pointer(ACTIVE_FILE, project=project,
                  project_path=str(Path(cwd).expanduser().resolve()),
                  session_note=rel)
    return {"saved": rel}


@mcp.tool()
def memory_note(type: str, scope: str, title: str, body: str,
                project: str | None = None,
                links: list[str] | None = None) -> dict:
    """Write a durable note (decision/architecture/convention/glossary/preference)."""
    path = notes_write.write_durable(_root(), type=type, scope=scope,
                                     title=title, body=body, project=project,
                                     links=links)
    return {"saved": str(path.relative_to(_root()))}


@mcp.tool()
def memory_promote(session_path: str, as_type: str) -> dict:
    """Promote a session insight into a durable note linking back to its origin."""
    path = notes_write.promote(_root(), session_path, as_type=as_type)
    return {"saved": str(path.relative_to(_root()))}


@mcp.tool()
def memory_define_project(slug: str, marker_dir: str | None = None) -> dict:
    """Register a new project; optionally drop a committed .agentmemory marker."""
    md = Path(marker_dir).expanduser().resolve() if marker_dir else None
    notes_write.define_project(_root(), slug, marker_dir=md)
    return {"defined": slug}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add a console entry point**

In `pyproject.toml`, under `[project]`, add:

```toml
[project.scripts]
agent-memory = "agent_memory.server:main"
```

- [ ] **Step 3: Verify the server imports and registers tools**

Run:
```bash
uv run python -c "from agent_memory.server import mcp; import asyncio; print(sorted(t.name for t in asyncio.run(mcp.list_tools())))"
```
Expected: a list of all 10 tool names:
```
['memory_checkpoint', 'memory_define_project', 'memory_list_projects', 'memory_note', 'memory_promote', 'memory_read', 'memory_recent', 'memory_resume', 'memory_search', 'memory_traverse']
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (≈ 27 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_memory/server.py pyproject.toml
git commit -m "feat: MCP server wiring 10 memory tools"
```

---

## Task 11: Mechanical snapshot script

**Files:**
- Create: `scripts/mechanical_snapshot.py`

This is the abrupt-power-off backstop. It needs **no** LLM and **no** Claude — it
reads the active pointer, captures git mechanical state of the active project, and
appends/updates a `## Mechanical snapshot` section in the active session note.

- [ ] **Step 1: Implement `scripts/mechanical_snapshot.py`**

```python
#!/usr/bin/env python3
"""Append git mechanical state of the active project to its session note.

Run by launchd on a timer and by Claude Code Stop/PreCompact hooks. Safe to run
when no session is active (it just exits).
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_memory.active import read_pointer       # noqa: E402
from agent_memory.config import ACTIVE_FILE, vault_root  # noqa: E402

_MARK = "## Mechanical snapshot"


def _git(cwd: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", cwd, *args],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    ptr = read_pointer(ACTIVE_FILE)
    if not ptr:
        return 0
    repo = ptr["project_path"]
    note_path = vault_root() / ptr["session_note"]
    if not note_path.exists():
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    status = _git(repo, "status", "--short") or "(clean)"
    diffstat = _git(repo, "diff", "--stat") or "(no unstaged changes)"

    block = (f"{_MARK}\n_Auto-captured {stamp}_\n\n"
             f"- Branch: `{branch}`\n\n"
             f"```\n{status}\n```\n\n"
             f"<details><summary>diff --stat</summary>\n\n"
             f"```\n{diffstat}\n```\n</details>\n")

    text = note_path.read_text()
    if _MARK in text:
        text = text[:text.index(_MARK)].rstrip() + "\n\n" + block
    else:
        text = text.rstrip() + "\n\n" + block
    note_path.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test the script end-to-end**

Run:
```bash
cd ~/Desktop/agent-memory
# Seed an active session pointing at this very repo, then snapshot it.
uv run python -c "
from pathlib import Path
from agent_memory import vault, sessions, active
from agent_memory.config import vault_root, ACTIVE_FILE
root = vault_root(); vault.scaffold(root)
p = sessions.checkpoint(root, project='agent-memory', task='Build memory system', summary='scaffolding')
active.write_pointer(ACTIVE_FILE, project='agent-memory', project_path='$PWD', session_note=str(p.relative_to(root)))
print('seeded', p)
"
uv run python scripts/mechanical_snapshot.py
echo "--- snapshot section now in the session note ---"
uv run python -c "
from agent_memory.config import vault_root, ACTIVE_FILE
from agent_memory.active import read_pointer
ptr = read_pointer(ACTIVE_FILE); print((vault_root()/ptr['session_note']).read_text())
"
```
Expected: the printed note contains a `## Mechanical snapshot` section with the current branch (`feature/agent-memory-system`) and git status.

- [ ] **Step 3: Commit**

```bash
git add scripts/mechanical_snapshot.py
git commit -m "feat: mechanical snapshot backstop script"
```

---

## Task 12: launchd timer

**Files:**
- Create: `launchd/com.krishna.agentmemory.snapshot.plist`

- [ ] **Step 1: Create the plist**

Create `launchd/com.krishna.agentmemory.snapshot.plist` with the literal repo path
and the `uv` path below (confirm the `uv` path matches `which uv` first):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.krishna.agentmemory.snapshot</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Library/Frameworks/Python.framework/Versions/3.13/bin/uv</string>
    <string>run</string>
    <string>python</string>
    <string>scripts/mechanical_snapshot.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/krishna.champaneria/Desktop/agent-memory</string>
  <key>StartInterval</key>
  <integer>600</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardErrorPath</key>
  <string>/tmp/agentmemory.snapshot.err</string>
  <key>StandardOutPath</key>
  <string>/tmp/agentmemory.snapshot.out</string>
</dict>
</plist>
```

Note: confirm the `uv` path matches `which uv` (the spec's environment probe showed
`/Library/Frameworks/Python.framework/Versions/3.13/bin/uv`). If different, update
the first `<string>` in `ProgramArguments`.

- [ ] **Step 2: Install and load the launchd agent**

Run:
```bash
mkdir -p ~/Library/LaunchAgents
cp ~/Desktop/agent-memory/launchd/com.krishna.agentmemory.snapshot.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.krishna.agentmemory.snapshot.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.krishna.agentmemory.snapshot.plist
launchctl list | grep agentmemory
```
Expected: a line containing `com.krishna.agentmemory.snapshot`.

- [ ] **Step 3: Verify it ran at load**

Run: `cat /tmp/agentmemory.snapshot.err`
Expected: empty (no errors). The active session note from Task 11 gets a refreshed
snapshot timestamp.

- [ ] **Step 4: Commit**

```bash
git add launchd/com.krishna.agentmemory.snapshot.plist
git commit -m "feat: launchd timer for periodic mechanical snapshots"
```

---

## Task 13: Register the server with Claude + smoke test

**Files:** none (modifies Claude's MCP config via CLI)

- [ ] **Step 1: Register the MCP server (user scope)**

Run:
```bash
claude mcp add agent-memory -s user -- uv --directory /Users/krishna.champaneria/Desktop/agent-memory run agent-memory
```

- [ ] **Step 2: Confirm registration**

Run: `claude mcp list`
Expected: `agent-memory` appears and shows a successful connection.

- [ ] **Step 3: Manual tool smoke test**

In a Claude session, ask: *"Call memory_list_projects for this folder."*
Expected: returns `known` (includes `agent-memory`) and `signals` with this repo's
git remote. Then ask it to `memory_checkpoint` a test task and confirm a file
appears under `~/Documents/agentMemory/sessions/agent-memory/`.

- [ ] **Step 4: Commit (if any config files are tracked in-repo)**

```bash
git commit --allow-empty -m "chore: register agent-memory MCP server"
```

---

## Task 14: Stop / PreCompact hooks

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Add hooks to `.claude/settings.json`**

Replace the file contents with (preserving the existing `permissions` block):

```json
{
  "permissions": {
    "allow": [
      "Bash(python -c ' *)"
    ]
  },
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /Users/krishna.champaneria/Desktop/agent-memory && uv run python scripts/mechanical_snapshot.py"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "cd /Users/krishna.champaneria/Desktop/agent-memory && uv run python scripts/mechanical_snapshot.py"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify hook JSON is valid**

Run: `uv run python -c "import json; json.load(open('.claude/settings.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 3: Verify the hook fires on session stop**

In a fresh Claude session in this repo, send any message, let it finish, then check:
Run: `cat /tmp/agentmemory.snapshot.err`
Expected: still empty; the active session note shows an updated snapshot timestamp.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: Stop/PreCompact hooks trigger mechanical snapshot"
```

---

## Task 15: Portable `agent-memory` skill

**Files:**
- Create: `.claude/skills/agent-memory/SKILL.md`, `.claude/skills/agent-memory/README.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: agent-memory
description: Use at the start of every session and throughout work in this project — gives the agent persistent memory via the agent-memory MCP server. Resume prior context, checkpoint working state, and record durable decisions in the Obsidian-backed knowledge graph.
---

# Agent Memory Protocol

You have a persistent memory served by the `agent-memory` MCP server, backed by an
Obsidian vault. Follow this protocol.

## At session start (before doing work)

1. Call `memory_list_projects` with the current working directory.
2. Decide the project from `known` + `signals`:
   - If a `marker` signal is present, use it.
   - Else if a `git_remote` matches a known project, use that.
   - **If it is ambiguous or appears new, ASK the user**: "Is this `<best-guess>`,
     or a new project?" If new, call `memory_define_project`.
3. Call `memory_resume(project)` and read the brief. You are now caught up — do not
   ask the user to re-explain prior context that the brief already covers.

## While working — checkpoint often (this is the whole point)

Call `memory_checkpoint(project, task, summary, files?, next_steps?, open_questions?)`:

- After completing any meaningful step or sub-task.
- Right after making a decision.
- Before any risky or large change.
- Whenever the user says "checkpoint" / "remember this".

Checkpoints are idempotent per task — calling repeatedly updates the same note, so
checkpoint freely. Each call writes to disk immediately, which is what survives an
abrupt power-off.

## Recording durable knowledge

- A lasting decision → `memory_note(type="decision", scope="project", ...)`.
- A cross-project preference or convention → `memory_note(scope="global", ...)`.
- A session insight worth keeping → `memory_promote(session_path, as_type)`.

## Catching mistakes

Before acting on something that smells like a prior decision (auth, storage,
naming), `memory_search(query, type="decision")` first. If the user's new request
contradicts a recorded decision, surface it: "We previously decided X (see <note>) —
do you want to override that?"

## Retrieval discipline (keep context clean)

- Start with `memory_search` / `memory_resume` — they return snippets/briefs.
- Only `memory_read` a full note when a snippet looks directly relevant.
- Use `memory_traverse` to follow `[[links]]` when you need related context.
```

- [ ] **Step 2: Write `README.md`**

```markdown
# agent-memory skill + hooks

Drop this skill into any project's `.claude/skills/` to make its agents speak to
your shared memory server.

## One-time global install (the server)

```bash
# from the agent-memory repo
claude mcp add agent-memory -s user -- \
  uv --directory /Users/krishna.champaneria/Desktop/agent-memory run agent-memory
```

Install the periodic snapshot timer:

```bash
cp launchd/com.krishna.agentmemory.snapshot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.krishna.agentmemory.snapshot.plist
```

## Per-project (copy these in)

1. Copy `.claude/skills/agent-memory/` into the target project's `.claude/skills/`.
2. Merge the `Stop` and `PreCompact` hooks from this repo's `.claude/settings.json`
   into the target project's `.claude/settings.json`.

The server is global (installed once); only the skill + hooks travel per project.
```

- [ ] **Step 3: Verify the skill frontmatter is valid**

Run:
```bash
uv run python -c "t=open('.claude/skills/agent-memory/SKILL.md').read(); assert t.startswith('---') and 'name: agent-memory' in t; print('skill frontmatter ok')"
```
Expected: `skill frontmatter ok`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/agent-memory/
git commit -m "feat: portable agent-memory skill + README"
```

---

## Task 16: Final verification

- [ ] **Step 1: Full test suite green**

Run: `uv run pytest -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 2: Server lists all 10 tools**

Run:
```bash
uv run python -c "from agent_memory.server import mcp; import asyncio; print(len(asyncio.run(mcp.list_tools())), 'tools')"
```
Expected: `10 tools`

- [ ] **Step 3: End-to-end resume check**

In a Claude session: checkpoint a task, then start a *new* session in the same repo
and confirm `memory_resume` rehydrates the task without you re-explaining it.

- [ ] **Step 4: Update the spec status**

In `docs/superpowers/specs/2026-06-10-agent-memory-system-design.md`, change
`Status:` to `Implemented (v1)`.

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "docs: mark agent memory v1 implemented"
```

---

## Deferred (not in this plan — per spec §11)

- **v2 — embeddings:** add `semantic: true` to `memory_search` via `fastembed`
  (ONNX) + SQLite-vec, with `Qwen3-Embedding 0.6B` as the embedding model.
- **v3 — local LLM librarian:** optional Ollama-backed distillation behind
  `memory_resume`; start with `Qwen3 4B` (16 GB-friendly), fall back to `Qwen3 8B`
  only if 4B distillation is too weak. Thinking mode OFF for latency.
