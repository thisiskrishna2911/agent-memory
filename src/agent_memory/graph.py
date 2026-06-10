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
