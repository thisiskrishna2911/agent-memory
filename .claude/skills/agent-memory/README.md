# agent-memory skill + hooks

Drop this skill into any project's `.claude/skills/` to make its agents speak to
your shared memory server.

## One-time global install (the server)

```bash
# from the agent-memory repo
claude mcp add agent-memory -s user -- \
  uv --directory /Users/krishna.champaneria/Desktop/agent-memory run agent-memory
```

Install the periodic snapshot timer:

```bash
cp launchd/com.krishna.agentmemory.snapshot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.krishna.agentmemory.snapshot.plist
```

## Per-project (copy these in)

1. Copy `.claude/skills/agent-memory/` into the target project's `.claude/skills/`.
2. Merge the `Stop` and `PreCompact` hooks from this repo's `.claude/settings.json`
   into the target project's `.claude/settings.json`.

The server is global (installed once); only the skill + hooks travel per project.
