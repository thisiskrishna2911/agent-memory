# Agent Memory System — Design Spec

**Date:** 2026-06-10
**Status:** Approved design — pending implementation plan
**Project root:** `~/Desktop/agent-memory/` (git: `krishna-videosdk/claude`)
**Vault:** `~/Documents/agentMemory` (existing Obsidian vault)

## 1. Problem & Goal

The user loses hours of in-progress context when the PC is turned off before a
session is saved, forcing them to re-explain ongoing work to the agent. They want
a **state-of-the-art memory system** backed by an **Obsidian vault**, exposed to
Claude (and any MCP-capable tool) through a **local MCP server**.

Goals:

- **Resumable working context** — a fresh session can pick up exactly where the
  last one left off, with no re-explaining.
- **Long-term knowledge graph** — durable architecture, decisions, conventions,
  and preferences accumulate over time so the agent stays consistent and can
  **catch mistakes** (e.g. flag an action that contradicts a prior decision).
- **Clean context** — the agent retrieves only the relevant slice of memory, never
  the whole vault.
- **Graph-based exploration** — leverage Obsidian's `[[wikilinks]]` so the agent
  can traverse related memory.

Both memory classes (working context + durable knowledge) matter **equally**.
Memory has **both global and per-project scope**. Writes happen **automatically on
triggers** (not dependent on the user remembering to save).

## 2. Architecture Overview

```
┌──────────────┐   MCP    ┌────────────────────┐   FS    ┌─────────────────────┐
│ Claude / any │ <──────> │  agent-memory MCP  │ <─────> │  Obsidian vault     │
│ MCP-capable  │  tools   │  server (Python)   │  r/w    │  ~/Documents/       │
│ tool         │          │                    │         │  agentMemory        │
└──────────────┘          └────────────────────┘         └─────────────────────┘
                                  ▲
                                  │ periodic checkpoint (launchd)
                                  │ Stop / PreCompact hooks
```

- The MCP server is the **only** interface the agent talks to.
- The vault is plain Markdown + YAML frontmatter; Obsidian merely *views* the same
  files. The server reads/writes the filesystem directly and does **not** depend on
  Obsidian running.

### Retrieval strategy (chosen direction)

Build in layers:

- **v1 — Agent-driven graph traversal (no extra infra).** The server exposes
  primitives (search, read, traverse, resume). Claude itself decides what to pull
  and walks the graph. Context stays clean because search/traverse return snippets;
  full notes are fetched only on demand.
- **v2 — Local embedding recall (reserved, additive).** A small local embedding
  model (`fastembed`, ONNX, ~100MB) indexes notes into SQLite-vec; `memory_search`
  gains an optional `semantic: true` — no signature change, no rewrite.
- **v3 — Local LLM "librarian" (optional).** Only if context bloat proves real:
  Ollama + a small model behind `memory_resume` to return distilled briefs.

## 3. Data Model (Vault Structure)

```
agentMemory/
├── index.md                     # root MOC; deterministic traversal entry point
├── global/                      # scope: global (the user, across all work)
│   ├── preferences.md
│   ├── conventions.md
│   └── people-glossary.md
├── projects/
│   └── <project-slug>/
│       ├── _moc.md              # project hub note
│       ├── architecture.md
│       ├── decisions/           # one ADR-style note per decision
│       │   └── 2026-06-10-use-mcp-for-memory.md
│       ├── conventions.md
│       └── glossary.md
└── sessions/
    └── <project-slug>/
        └── 2026-06-10T1430-feature-x.md   # working-context snapshots
```

**Two memory classes, different lifecycles:**

- **Sessions** (fast-changing): snapshot of *what is actively being worked on* —
  task, files touched, decisions in flight, next steps, open questions. Written
  **periodically** so an abrupt power-off loses minimal work.
- **Durable knowledge** (slow-changing): architecture, decisions, conventions,
  glossary, preferences. Promoted from sessions when something proves lasting.

**Frontmatter schema** (powers search + scope filtering):

```yaml
---
type: session | decision | architecture | convention | preference | glossary
scope: global | project
project: <project-slug>          # omitted for global
status: active | resolved | superseded
created: 2026-06-10T14:30
updated: 2026-06-10T15:10
tags: [feature-x, auth, bug]
links: ["[[architecture]]", "[[2026-06-09T1100-feature-x]]"]
---
```

**Graph wiring:** every session links to the project `_moc.md`, to relevant
decisions, and to the **previous** session for the same feature, so following
`[[wikilinks]]` reconstructs a timeline. `index.md → project MOC → decisions/
sessions` gives a deterministic traversal start point.

## 4. Project Identity Resolution (agent-mediated)

Memory must **not** be keyed off the directory path: the same project lives in many
folders (clones / worktrees / machines), and all must resolve to **one** identity →
one shared memory.

Resolution is **owned by the agent**, with the user as tiebreaker:

- The server surfaces signals and the known list; the agent reasons and asks the
  user when unsure.
- At session start the agent calls `memory_list_projects`, picks the best match,
  and if ambiguous or new, **asks**: *"Is this `feature-x`, or a new project?"*
- The choice is remembered afterward (optionally via a committed `.agentmemory`
  marker so the slug travels with the repo).

This avoids brittle auto-keying while still collapsing multiple instances of the
same project to one memory.

## 5. MCP Server Interface (Tools)

Small, well-bounded tools — each one job. Clean context is enforced by returning
**titles + snippets first, full bodies only on demand**.

**Read / retrieval**

| Tool | Input | Returns | Purpose |
|------|-------|---------|---------|
| `memory_list_projects` | (cwd) | known slugs + detected signals (remote, folder, marker) | agent resolves / confirms identity |
| `memory_search` | `query`, `scope?`, `project?`, `type?`, `limit?`, `semantic?` (v2) | ranked `{title, path, snippet, tags}` | default discovery; full-text + frontmatter filter |
| `memory_read` | `path` | full note body + frontmatter | pull one note once relevant |
| `memory_traverse` | `path`, `depth?` (default 1) | neighbor notes via `[[links]]` + snippets | walk the graph |
| `memory_resume` | `project?` | latest N sessions + linked decisions, bounded brief | one-shot rehydrate ("pick up where I left off") |
| `memory_recent` | `project?`, `limit?` | recent sessions/decisions by `updated` | timeline view |

**Write**

| Tool | Input | Behavior |
|------|-------|----------|
| `memory_checkpoint` | `project`, `task`, `summary`, `files?`, `next_steps?`, `open_questions?` | create/update the current session snapshot; **idempotent per active task** |
| `memory_note` | `type`, `scope`, `project?`, `title`, `body`, `links?` | write a durable note; auto frontmatter + backlinks |
| `memory_promote` | `session_path`, `as_type` | turn a proven session insight into a durable note, linking back to origin |
| `memory_define_project` | `slug`, `signals?` | register a new project; optionally drop `.agentmemory` marker |

**Principles baked in:** scope-aware by default (project inferred from cwd),
snippets before bodies, idempotent checkpoints (periodic saves don't litter the
vault), embedding hook reserved (v2 additive).

## 6. Auto-Capture & Triggers (defense in depth)

The original pain is an abrupt power-off before a save. Multiple independent
triggers so no single miss is costly:

1. **Periodic background checkpoint (the safety net).** A launchd agent (or server
   timer) checkpoints every **N minutes (default 10)** while a task is active.
   Idempotent, so it just refreshes the current session note. **This is what
   survives an abrupt power-off** — worst case ~10 min lost, not hours. This is the
   backbone, not an afterthought.
2. **Event triggers via Claude Code hooks.** `Stop` / `SessionEnd` → checkpoint on
   clean exit; `PreCompact` → checkpoint before context compaction.
3. **Agent-initiated checkpoints.** Claude checkpoints at semantic boundaries
   (sub-task done, decision made, before risky change) — captures *meaning*.
4. **Manual.** User says "checkpoint" / "remember this" anytime.

**What a checkpoint captures:** active task + goal, files touched, decisions
(linked), next steps, open questions, link to previous session.

**Honest limitation:** triggers 2–4 cannot fire if the machine is killed
mid-thought — only **trigger 1 (periodic)** protects against that.

## 7. Retrieval Flows

- **Resume after a lost session:** open folder → `memory_list_projects` (ask only
  if ambiguous) → `memory_resume(project)` returns a compact brief (task, files,
  next steps, open questions) → agent caught up in one call; deeper context via
  opt-in `memory_traverse`.
- **Mid-work recall:** `memory_search("auth decision", type=decision)` → snippets →
  `memory_read` the relevant one → optional `traverse`.
- **Catching a mistake:** decisions are durable notes; when an action contradicts
  one, search surfaces the conflicting decision and the agent flags it.

**Context-cleanliness contract:** search/traverse return snippets only; full notes
only via `memory_read`; `memory_resume` returns a bounded brief (latest K sessions);
v2 `recall` returns top-k chunks, not whole notes.

## 8. Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| MCP server | **Python + `uv`**, official MCP SDK | `uv`/Python 3.13 present; easy vault + frontmatter handling; easy to extend with embeddings |
| Vault access | Direct filesystem r/w on `~/Documents/agentMemory` | no dependency on Obsidian running |
| Search (v1) | frontmatter parse + full-text + tag filter, in-process | no infra; fast for a personal vault |
| Graph | parse `[[wikilinks]]` → neighbor map on demand | native Obsidian structure |
| Periodic checkpoint | macOS **launchd** agent (plist) → small script | OS-level reliability; survives even if Claude isn't active |
| Hooks | Claude Code `Stop` / `PreCompact` in settings | event-driven saves |
| Embeddings (v2) | local `fastembed` (ONNX, ~100MB) → SQLite-vec | semantic recall, no server, no Ollama |
| Local LLM (v3, optional) | Ollama + small model behind `memory_resume` | only if context bloat proves real |

## 9. Deliverables & Portability

Two artifact types with different homes:

1. **MCP server — global infrastructure (runs once, serves every project).** A real
   codebase in this repo. Registered once in Claude; **not** copied per-folder.
   Includes server code, launchd plist, install script, this spec.
2. **Portable skill + hooks — copied into any project as needed.** Staged in this
   repo's `.claude/`:
   - `.claude/skills/agent-memory/SKILL.md` — teaches the memory **protocol**: at
     session start `memory_list_projects` → confirm project → `memory_resume`;
     checkpoint at semantic moments; check decisions before contradicting them; how
     to write durable notes.
   - `.claude/settings.json` — `Stop` + `PreCompact` hooks that fire
     `memory_checkpoint`, ready to merge into a project's settings.
   - A short `README` in the skill folder: how to install the server + copy these in.

Separation: heavy infra installed once; thin protocol layer travels freely. Drop
the `agent-memory` skill + hooks into any project's `.claude/` and its agents
immediately speak to the one shared memory server.

## 10. Build Order

1. Vault scaffold (folders, `index.md`, frontmatter conventions).
2. MCP server — read tools (`list_projects`, `search`, `read`, `traverse`,
   `resume`, `recent`).
3. MCP server — write tools (`checkpoint`, `note`, `promote`, `define_project`).
4. Wire into Claude (`.claude.json` / `claude mcp add`).
5. Periodic launchd checkpoint + Claude Code `Stop`/`PreCompact` hooks.
6. Portable `agent-memory` skill + hooks staged in `.claude/`.
7. *(v2)* embeddings; *(v3)* local LLM.

## 11. Out of Scope (v1 — YAGNI)

- Local LLM librarian (deferred to v3).
- Embedding/vector index (deferred to v2, but interface reserved).
- Cross-tool sync beyond MCP (any MCP-capable tool already benefits).
- Multi-user / shared-team memory.
