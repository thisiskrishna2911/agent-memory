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
