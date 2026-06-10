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
        if self.title:
            meta["title"] = self.title
        meta["created"] = self.created
        meta["updated"] = self.updated
        if self.tags:
            meta["tags"] = self.tags
        if self.links:
            meta["links"] = self.links
        return meta
