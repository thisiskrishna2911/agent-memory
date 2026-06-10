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
