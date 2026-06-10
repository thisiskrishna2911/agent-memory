---
name: agent-memory
description: Use at the start of every session and throughout work in this project — gives the agent persistent memory via the agent-memory MCP server. Resume prior context, checkpoint working state, and record durable decisions in the Obsidian-backed knowledge graph.
---

# Agent Memory Protocol

You have a persistent memory served by the `agent-memory` MCP server, backed by an
Obsidian vault. Follow this protocol.

## At session start (before doing work)

1. Call `memory_list_projects` with the current working directory.
2. Decide the project from `known` + `signals`:
   - If a `marker` signal is present, use it.
   - Else if a `git_remote` matches a known project, use that.
   - **If it is ambiguous or appears new, ASK the user**: "Is this `<best-guess>`,
     or a new project?" If new, call `memory_define_project`.
3. Call `memory_resume(project)` and read the brief. You are now caught up — do not
   ask the user to re-explain prior context that the brief already covers.

## While working — checkpoint often (this is the whole point)

Call `memory_checkpoint(project, task, summary, files?, next_steps?, open_questions?)`:

- After completing any meaningful step or sub-task.
- Right after making a decision.
- Before any risky or large change.
- Whenever the user says "checkpoint" / "remember this".

Checkpoints are idempotent per task — calling repeatedly updates the same note, so
checkpoint freely. Each call writes to disk immediately, which is what survives an
abrupt power-off.

## Recording durable knowledge

- A lasting decision → `memory_note(type="decision", scope="project", ...)`.
- A cross-project preference or convention → `memory_note(scope="global", ...)`.
- A session insight worth keeping → `memory_promote(session_path, as_type)`.

## Catching mistakes

Before acting on something that smells like a prior decision (auth, storage,
naming), `memory_search(query, type="decision")` first. If the user's new request
contradicts a recorded decision, surface it: "We previously decided X (see <note>) —
do you want to override that?"

## Retrieval discipline (keep context clean)

- Start with `memory_search` / `memory_resume` — they return snippets/briefs.
- Only `memory_read` a full note when a snippet looks directly relevant.
- Use `memory_traverse` to follow `[[links]]` when you need related context.
