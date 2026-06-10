"""Detect ghost links: wikilinks whose target note does not exist.

A ghost link is a `[[target]]` (in a note's body or its frontmatter `links`)
that resolves to no file in the vault — Obsidian renders these as dangling
nodes in the graph. Agents should resolve them right after writing.
"""
from __future__ import annotations

from pathlib import Path

from .graph import _resolve, extract_links
from .vault import read_note


def find_ghost_links(vault_root: Path, rel_path: str) -> list[str]:
    """Return wikilink targets in the note at rel_path that resolve to no file.

    Checks both body `[[links]]` and frontmatter `links` entries. Returns the
    bare targets (no brackets), in first-seen order, de-duped.
    """
    note_file = vault_root / rel_path
    if not note_file.exists():
        return []
    note = read_note(note_file)
    targets: list[str] = list(extract_links(note.body))
    for entry in note.links:  # frontmatter links stored like "[[architecture]]"
        for target in extract_links(entry):
            if target not in targets:
                targets.append(target)
    return [t for t in targets if _resolve(vault_root, t) is None]
