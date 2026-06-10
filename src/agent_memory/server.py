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
