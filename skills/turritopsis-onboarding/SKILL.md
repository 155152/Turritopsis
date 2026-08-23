---
name: turritopsis-onboarding
description: Orient an agent in a long-running project backed by Turritopsis, retrieve only the relevant project truth, fill scan-created knowledge skeletons, preserve evidence and attribution, and hand work off without replaying prior chats. Use when a repository contains .turritopsis/stages.json, when joining or resuming a Turritopsis-managed project, or when asked to update, verify, brief, or maintain its shared project knowledge.
---

# Turritopsis Onboarding

Use Turritopsis as the project map, not as a replacement for live evidence. Route first, read narrowly, and record only what the repository or a named human source supports.

## Arrive

1. Run `turritopsis brief` when the CLI and project checkout are available.
2. With MCP, call `list_stages` for the map, `search_stages` for the current task, then `get_stage` for the few relevant Stages.
3. Read any surfaced human handoff before asking questions. Treat it as authoritative about intent and priorities, but verify claims about current code.
4. Do not open the entire JSON store merely to discover where knowledge lives.

## Split the remaining work

- Treat filled, verified Stages as settled routing context. Recheck them only when the task or current diff can invalidate them.
- Fill self-serve skeletons from the cited repository paths and their live dependencies.
- Ask a person only for knowledge the repository cannot contain: rejected designs, red lines, manual recovery habits, ownership, or unresolved anomaly judgement.
- Treat `scan-anomalies.json` as review leads, never canonical truth. Confirm a finding before using it in a Stage.

## Write safely

Use `update_stage` with the Stage's current revision, a specific actor, and the smallest complete body change. Preserve the standard routing fields:

```text
Purpose: ...
Search hints: ...
Summary: ...
Verified: YYYY-MM-DD by <source>
Status: current|historical|generated|unresolved
Authority: ...
```

Leave an explicit placeholder when evidence is insufficient. Never turn a plausible inference or an anomaly into canonical fact.

## Maintain and hand off

- Run `turritopsis maintain --model <cheap-model>` for evidence-based routine maintenance; use proposal mode when human approval is required.
- Use the Web UI for human directional edits and MCP for agent retrieval and precise updates.
- Before leaving, update the durable Stage that owns the current decision, blocker, or next step. Do not create a separate agent-memory layer or chat transcript dump.
- Keep the MCP surface to `list_stages`, `search_stages`, `get_stage`, and `update_stage`; use CLI commands for scan, briefing, anomalies, export, scheduling, and maintenance.
