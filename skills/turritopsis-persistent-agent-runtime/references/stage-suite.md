# Persistent Agent runtime Stage suite

Use this suite for assistants or agents that stay online, resume a durable session, receive scheduled wakes, use tools, or communicate through one or more relays and channels.

## Core responsibilities

- `orientation` — Give the operator a short body map, primary entry points, and the first safe place to inspect.
- `authority` — Identify live process, active session, queue, durable state, configuration, deployment source, mirrors, generated snapshots, and conflict precedence.
- `architecture` — Map session/model, supervisor, relay, channel adapters, scheduler, tool boundary, memory, and storage by ownership and dependency direction.
- `flow` — Separate inbound message, scheduled wake, tool action, outbound reply, persistence, restart, and recovery lifecycles.
- `contract` — Define tool, MCP, channel, queue, wake, acknowledgement, timeout, retry, and terminal-result semantics.
- `boundary` — Distinguish ordinary service operation from context-destructive session reset, replacement, cursor mutation, queue rewrites, or identity changes.
- `operations` — Give diagnosis, safe restart, degraded-mode, restore, rollback, and post-action smoke procedures.
- `verification` — Prove process health, transport health, channel delivery, tool reachability, persistence, and end-to-end behavior separately.
- `incident` — Preserve loops, disconnects, duplicate wakeups, stale cursors, context loss, hidden retry storms, and false-green health checks.
- `handoff` — Keep active session constraints, current incident, next safe action, and actions requiring human approval current.
- `generated_inventory` — Store current versions, process IDs, session IDs, listener inventory, hashes, or schedule revisions only when deterministically refreshed.
- `history` and `decision` — Keep retired topology and consequential continuity choices away from current runbooks.

## Judgment rules

- Process alive, transport connected, channel delivering, and end-to-end useful are different claims. Verify and store them separately.
- A local clone, generated status page, or review mirror is not live authority unless the deployment contract says so.
- Restarting an ordinary adapter is not the same as replacing the model session or advancing a durable command cursor. Name the blast radius.
- Current topology and retired topology belong in separate Stages. Never make an operator reverse-engineer tense.
- Offline evidence means runtime state may be unknown. Do not label the product broken without a requested live check.
- A scheduler firing does not prove the Agent processed the wake. Preserve acknowledgement and terminal evidence.
- A tool call returning does not prove its external effect. Define receipts or independent observation.
- Recovery guidance must protect durable state and state which operations need explicit human authority.

## Common bad shapes

- `runtime.everything` combines topology, current IDs, restart commands, incidents, and old migrations.
- A green process supervisor is reported as a successful human-facing reply path.
- Generic “restart the Agent” instructions silently create a new session and lose context.
- Docs describe the intended port or path while the live process differs.
- Old session identifiers remain in a stable architecture Stage and become stale immediately.

## Strong Stage body

Lead with the operational answer and scope. Name the live authority, dependency direction, health layer, safe action, protected state, proof of success, rollback point, and approval gate. Add triggers for session, supervisor, relay, queue, channel, tool, scheduler, persistence, or deployment changes.
