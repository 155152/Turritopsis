---
name: turritopsis-onboarding
description: Scan and map a software project with the currently installed Agent, design durable project-specific Stages, validate and apply skeletons, retrieve only relevant truth, and maintain evidence-backed knowledge without replaying chats or sending repository evidence to a second LLM. Use when joining, resuming, initializing, briefing, or maintaining a Turritopsis-managed project.
---

# Turritopsis Onboarding

Use the installed Agent as the classifier and writer. Keep scanning local and deterministic; never require a second model or API key for onboarding.

## Cold start

1. Run `turritopsis scan`. Reuse existing `scan-evidence.json` unless the repository changed enough to justify `--refresh`.
2. Read `scan-run.json` first, then inspect coverage and omitted materials in `scan-evidence.json`. Do not assume the snapshot contains everything.
3. Read [stage-types.md](references/stage-types.md). Select one responsibility for each Stage.
4. Read [project-suites.md](references/project-suites.md). Choose the smallest suitable suite; combine suites for hybrids.
5. Inspect only the evidence needed to classify durable knowledge regions. Do not generate one Stage per file, directory, or document.
6. Write `skeleton.json` with `classification_provenance.source: installed-agent`, `agent_self_reported`, and an ISO-8601 timestamp. The Agent name is self-reported free text for debugging only; never use it as provider/model identity or trustworthy provenance.
7. Run `turritopsis apply-skeleton skeleton.json`. Fix every validation error instead of bypassing it.
8. Fill Stage bodies from repository evidence through `update_stage` with revision protection.

Use [paired-examples.md](references/paired-examples.md) when a Stage is structurally valid but vague. Use the seven fixtures when selecting a suite:

- [fixture-web-saas.json](references/fixture-web-saas.json)
- [fixture-library-sdk.json](references/fixture-library-sdk.json)
- [fixture-data-ml.json](references/fixture-data-ml.json)
- [fixture-mobile-desktop.json](references/fixture-mobile-desktop.json)
- [fixture-infrastructure.json](references/fixture-infrastructure.json)
- [fixture-embedded-iot.json](references/fixture-embedded-iot.json)
- [fixture-research-protocol.json](references/fixture-research-protocol.json)

Fixtures are examples, not templates. Replace their fictional evidence paths and choose only the types the target project needs.

## Write knowledge, not indexes

- Give each Stage one complete knowledge responsibility.
- Title it like a destination for a user question, not a directory name.
- Put the direct answer in `Summary`; do not begin with background.
- Separate current facts, decisions, history, incidents, and generated inventories.
- Cite paths plus symbols, schemas, commands, or real artifacts when available.
- Preserve conflicts and unknowns explicitly. Never smooth uncertainty into prose.
- Give one Stage Authority over each fact; route duplicates to that Stage.
- Split stable architecture from volatile handoff or runtime state.
- Add concrete update triggers so later Agents know when verification is necessary.

## Arrive and maintain

1. Run `turritopsis brief`, or use MCP in the order `list_stages` → `search_stages` → `get_stage`.
2. Treat verified Stages as routing context, not as a replacement for live evidence.
3. Treat anomaly output as leads requiring confirmation, never canonical truth.
4. Ask a person only for an unresolved judgement the repository and supplied materials cannot answer.
5. Use `update_stage` with the current revision, a named actor, and the smallest complete body change.
6. Before leaving, update the Stage that owns the current decision, blocker, or next step. Do not create a separate chat-memory dump.
