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
