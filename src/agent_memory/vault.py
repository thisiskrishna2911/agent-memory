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
    """Load a Note from disk. Title from frontmatter, then first heading, then filename."""
    meta, body = parse(path.read_text())
    title = meta.get("title") or _title_from(body, path)
    return Note(
        type=meta.get("type", "note"),
        scope=meta.get("scope", "global"),
        project=meta.get("project"),
        status=meta.get("status"),
        title=title,
        body=body,
        created=meta.get("created", ""),
        updated=meta.get("updated", ""),
        tags=meta.get("tags", []) or [],
        links=meta.get("links", []) or [],
    )
