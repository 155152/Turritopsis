# Universal Stage contracts

Stage types describe a knowledge responsibility, not a required Current name. Select the fewest types that answer recurring project questions.

## Standard body

```markdown
# Title

Type: flow
Purpose: Which questions this Stage helps answer.
Search hints: Phrases a person or Agent would actually use.
Summary: Give the direct answer first.
Verified: YYYY-MM-DD by agent from repository evidence
Status: current
Authority: What this Stage owns and explicitly excludes.
Freshness: volatile | steady | historical | generated

## Knowledge

Compressed, complete, executable knowledge.

## Evidence

- `src/api.py` — `submit_request`
- `docs/protocol.md` — terminal-state contract

## Unknowns

- Facts that remain unconfirmed.

## Update triggers

- API schema changes.
- Worker ownership changes.
```

## Types

### `orientation`

Answer what the project is, who it serves, where to start reading, and what is outside scope. Keep it short; exclude full architecture and commercial history.

### `authority`

Name the authoritative repositories, branches, directories, environments, and data sources. Mark mirrors, generated artifacts, archives, and conflict precedence.

### `architecture`

Explain components, responsibilities, dependency direction, process/package/service boundaries, state owners, and deliberate exclusions. Never reproduce the file tree.

### `flow`

Follow one complete request, event, data, or lifecycle path through entry, state changes, persistence/output, failure, retry, and terminal state. Do not list unrelated functions.

### `contract`

Own an API, CLI, file format, protocol, plugin surface, or SDK promise. State inputs, outputs, failure semantics, versioning, and compatibility boundaries.

### `domain`

Define core entities, terminology, states, invariants, and business rules. Separate similar concepts that newcomers commonly confuse.

### `data`

Own sources, schemas, storage, lineage, migration, backfill, restore, sensitivity, generated data, and disposable data.

### `boundary`

State invariants, fail-closed behavior, authorization gates, security/privacy limits, and apparently redundant compatibility or recovery mechanisms. Record repository-proven boundaries before asking for unwritten judgement.

### `operations`

Explain start, stop, diagnosis, first checks, health evidence, common recovery, and remaining manual actions.

### `verification`

Map tests to claims: what each proves, what it does not prove, environment prerequisites, minimum smoke, and PASS/FAIL/BLOCKED criteria.

### `build_release`

Own build inputs, artifact validation, version derivation, signing, release gates, rollback, and whether release is currently allowed.

### `handoff`

Record where work stopped, the blocker, the smallest next action, what not to repeat, and where results must be written back. Keep it short, current, and executable.

### `decision`

Record the problem, alternatives, chosen option, reasoning, assumptions, and conditions that should trigger reevaluation. Do not turn it into a timeline.

### `incident`

Record symptoms, root cause, misleading diagnostic paths, correction, and recurrence prevention. Link logs; do not paste them.

### `history`

Explain how the project became its current form. Keep historical facts out of current operational or architecture Stages.

### `generated_inventory`

Hold deterministic versions, dependencies, schema hashes, deployment revisions, or other mechanically regenerated facts. Mark it generated and safe to overwrite.

## Judgement rules

- Let one Stage own one complete knowledge region.
- Let one document support many Stages; never map documents one-to-one to Stages.
- Merge multiple materials into one Stage when they answer one question; preserve conflicts.
- Verify repository-answerable facts before asking a person.
- When documentation may be stale, bring the concrete conflict to a human for judgement.
- Never create `misc`, `notes`, `other`, or `general` drawers.
- Separate stable architecture from high-churn handoff/runtime state.
- Use `historical` only for evolution, `generated` only for deterministic output, and `volatile` only when change is expected frequently.
