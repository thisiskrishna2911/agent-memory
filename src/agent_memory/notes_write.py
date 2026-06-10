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
