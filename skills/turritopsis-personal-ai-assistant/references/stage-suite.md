# Personal AI assistant Stage suite

Use this suite for private assistants, companion agents, household helpers, creative partners, and tool-using assistants whose relationship with one person persists over time.

## Core responsibilities

- `orientation` — Define who the assistant serves, the relationship it offers, its primary channels, and what it is not authorized to be.
- `authority` — Separate human instructions and corrections, project policy, memory, runtime observation, model inference, and external-service state. Say which wins on conflict.
- `domain` — Define human, assistant, session, preference, commitment, task, consent, channel, and any meaningful relationship state.
- `boundary` — State autonomy levels, approval gates, private/public separation, sensitive actions, data egress, impersonation limits, and fail-closed behavior.
- `flow` — Trace message-to-reply, request-to-tool-action, proactive suggestion-to-consent, correction-to-memory, and interruption-to-recovery.
- `contract` — Define channel delivery, action receipts, partial failure, cancellation, proactive timing, and what the person is shown.
- `data` — Describe identity, preferences, commitments, conversation records, corrections, retention, and sensitive material without turning the Stage into a raw diary.
- `operations` — Explain channel diagnosis, safe recovery, degraded operation, continuity checks, and how to avoid destroying the current relationship context.
- `verification` — Prove what the human saw, what was actually sent or changed, which authority allowed it, and whether private data stayed inside its boundary.
- `decision` — Preserve consequential autonomy, privacy, tone, or memory choices and the assumptions that would reopen them.
- `handoff` — Keep the current human goal, promise, blocker, next safe action, and “do not redo” note concise.

Add `architecture`, `incident`, `history`, `build_release`, or `generated_inventory` only when the implementation makes them durable retrieval destinations.

## Judgment rules

- Relationship tone is not evidence that an external action completed. Store receipts and observable results separately.
- Affection, familiarity, or repeated behavior is not consent. Consequential actions need explicit and current authority.
- A preference is not an immutable identity fact. Record source, scope, correction path, and expiration when appropriate.
- The human-facing reason for a suggestion may omit private internal machinery; the scheduler may still use bounded internal state. Give each surface separate Authority.
- One channel being alive does not prove another delivered. Define per-channel delivery and fallback semantics.
- Let the human edit direction, boundaries, and meaning. Let agents maintain evidence-backed implementation detail.
- Ask the person for judgement only after repository, runtime, supplied materials, and existing Stages cannot settle it.
- Keep current commitments separate from relationship history. Historical warmth must not masquerade as an active promise.

## Common bad shapes

- `personality` owns consent, memory, tool permissions, and UI tone at once.
- “The assistant knows the user” hides evidence, correction, privacy, and retention.
- A successful model response is treated as proof that a message arrived or a device action occurred.
- Proactive behavior is described as “helpful” without timing, quiet hours, dismissal, or approval rules.
- Private scheduler state is printed verbatim to justify a user-facing suggestion.

## Strong Stage body

Begin with the human-facing promise or boundary. Name who may decide, which evidence proves the state, what the assistant may do without asking, what requires confirmation, and what failure looks like. Cite code, policy, runtime contracts, and visible receipts. Add triggers for channel, tool permission, memory, autonomy, privacy, or relationship-policy changes.
