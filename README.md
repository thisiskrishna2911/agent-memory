# agent-memory

A local **MCP server**, backed by an **Obsidian vault**, that gives Claude (and any
MCP-capable agent) persistent memory — so you never lose hours of context to an
abrupt power-off, and the agent can pick up exactly where you left off.

It stores two kinds of memory:

- **Sessions** — snapshots of what you're actively working on (task, files, next
  steps, open questions). The *resume* layer.
- **Durable knowledge** — architecture, decisions, conventions, glossary,
  preferences. The *knowledge graph* layer, wired together with Obsidian
  `[[wikilinks]]`.

Vault location: `~/Documents/agentMemory`.

## Why

The pain this solves: you forget to save a session, the PC turns off, and hours of
context are gone — you re-explain everything to the agent. agent-memory captures
working context **automatically and frequently**, writing to disk immediately, so a
power-off costs minutes, not hours.

## Architecture

```
┌──────────────┐   MCP    ┌────────────────────┐   files  ┌─────────────────────┐
│ Claude / any │ <──────> │  agent-memory      │ <──────> │  Obsidian vault     │
│ MCP tool     │  tools   │  server (Python)   │          │  ~/Documents/       │
└──────────────┘          └────────────────────┘          │  agentMemory        │
                                  ▲                        └─────────────────────┘
            periodic launchd timer │ + Stop/PreCompact hooks
                                  │
                         scripts/mechanical_snapshot.py
                       (git-state backstop, survives power-off)
```

- **Pure-Python core** (`src/agent_memory/`) holds all logic, unit-tested in
  isolation. **`server.py`** is a thin MCP adapter exposing 10 tools.
- Durability is **defense in depth**: the agent writes *semantic* checkpoints via
  the `memory_checkpoint` tool; a launchd timer + Claude Code hooks run a *mechanical*
  snapshot script (git status + diff of the active project) as a backstop. An
  "active session pointer" (`~/.agent-memory/active.json`) links the two.

## Requirements

- macOS (launchd timer), Python 3.13, [`uv`](https://docs.astral.sh/uv/)
- [Obsidian](https://obsidian.md/) (optional — only to *view* the vault; the server
  reads/writes files directly)

## Install

```bash
# 1. Install deps
cd ~/Desktop/agent-memory
uv sync

# 2. Register the MCP server with Claude (user scope = all sessions)
claude mcp add agent-memory -s user -- \
  uv --directory /Users/krishna.champaneria/Desktop/agent-memory run agent-memory
claude mcp list        # expect: agent-memory … ✔ Connected

# 3. Install the periodic snapshot timer (every 10 min, survives power-off)
cp launchd/com.krishna.agentmemory.snapshot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.krishna.agentmemory.snapshot.plist
launchctl list | grep agentmemory     # expect the label, exit code 0
```

The `Stop` / `PreCompact` hooks in `.claude/settings.json` fire the snapshot script
automatically when Claude finishes a turn or before context compaction.

## Usage

Drop the **`agent-memory` skill** into any project's `.claude/skills/` and the agent
follows the protocol automatically:

1. **At session start** → `memory_list_projects`, confirm the project (asking you if
   ambiguous), then `memory_resume` to rehydrate.
2. **While working** → `memory_checkpoint` often (idempotent per task).
3. **Durable knowledge** → `memory_note` for decisions/conventions; `memory_promote`
   to elevate a session insight.
4. **Catch mistakes** → `memory_search(type="decision")` before contradicting a prior
   decision.

See `.claude/skills/agent-memory/SKILL.md` for the full protocol.

## MCP tools

| Tool | Purpose |
|------|---------|
| `memory_list_projects` | Known project slugs + identity signals for the current folder |
| `memory_search` | Full-text + frontmatter-filtered search (returns snippets) |
| `memory_read` | Read one full note by vault-relative path |
| `memory_traverse` | Follow `[[wikilinks]]` N hops (snippets) |
| `memory_recent` | Recent sessions for a project, newest first |
| `memory_resume` | One-shot rehydration: latest session snapshots |
| `memory_checkpoint` | Create/update the active working-context snapshot (idempotent) |
| `memory_note` | Write a durable note (decision/architecture/convention/glossary/preference) |
| `memory_promote` | Promote a session insight into a durable note |
| `memory_define_project` | Register a new project (optional `.agentmemory` marker) |

## Project identity

Memory is **not** keyed off the directory path, so multiple clones/worktrees of the
same repo share one memory. The agent resolves identity from a committed
`.agentmemory` marker, the git remote, or the folder name — and asks you when it's
ambiguous.

## Portability

The MCP server is **global** (installed once, serves every project). Only the thin
protocol layer travels: copy `.claude/skills/agent-memory/` into a project and merge
the `Stop`/`PreCompact` hooks from `.claude/settings.json`. See
`.claude/skills/agent-memory/README.md`.

## Development

```bash
uv run pytest -q                       # run the test suite (32 tests)
uv run python -c "from agent_memory.server import mcp; import asyncio; \
  print(len(asyncio.run(mcp.list_tools())), 'tools')"
```

Tests use a throwaway vault via the `AGENT_MEMORY_VAULT` env var — they never touch
your real `~/Documents/agentMemory`.

## Roadmap (deferred)

- **v2 — semantic search + ranker.** Local embeddings (`Qwen3-Embedding 0.6B` via
  `fastembed`/SQLite-vec) behind an additive `semantic: true` flag on
  `memory_search`, with result ranking so retrieval never dumps unneeded context.
- **v3 — local LLM librarian.** Optional Ollama-backed distillation behind
  `memory_resume` (`Qwen3 4B`, thinking off) if context bloat proves real.

Design spec: `docs/superpowers/specs/2026-06-10-agent-memory-system-design.md`.
Implementation plan: `docs/superpowers/plans/2026-06-10-agent-memory-system.md`.
