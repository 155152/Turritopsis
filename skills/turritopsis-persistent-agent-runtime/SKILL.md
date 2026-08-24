---
name: turritopsis-persistent-agent-runtime
description: Design, review, or repair Turritopsis Stages for a long-running Agent runtime with sessions, relays, schedulers, tools, queues, channels, recovery, and continuity constraints. Use when operators must distinguish live authority from mirrors, process health from functional health, ordinary service restarts from identity or session replacement, and current runtime facts from historical topology.
---

# Turritopsis Persistent Agent Runtime

Map the Agent's operating body without confusing it with personality or memory.

1. Use `$turritopsis-onboarding` for local scanning and validated skeleton application.
2. Read [stage-suite.md](references/stage-suite.md).
3. Identify the live runtime authority before trusting configuration, documentation, a local clone, or a review mirror.
4. Separate model session, process, relay, channel, scheduler, tool layer, queue, and durable state by responsibility.
5. Protect identity or context continuity with an explicit boundary; do not hide session replacement inside a generic restart procedure.
6. Define health in layers: process, transport, channel, tool path, and end-to-end function.
7. Record degraded or offline state as unknown where evidence is unavailable; do not invent a failure.
8. Use [fixture.json](references/fixture.json) as a fictional quality example only.
