# Paired Stage examples

Use these pairs to distinguish a formatted placeholder from a useful knowledge destination. Each good example names the questions it routes and the changes that invalidate it.

## `orientation`

**Bad:** “This repository contains the Acme application and several modules.” It gives no audience, entry point, or scope boundary.

**Good:** “Acme Checkout accepts merchant order submissions and hands authorized orders to fulfillment. Start at `README.md` and `src/http/orders.py`; catalog search and warehouse routing are separate systems.” Routes “what is this?”, “where do I begin?”, and “is catalog owned here?”. Invalidated by scope or primary-entry changes.

## `authority`

**Bad:** “Production is on the server; code is on GitHub.” It gives no precedence.

**Good:** “`acme/checkout` main is source authority; `deploy/rendered/` is generated; production schema observed through migration revision is runtime authority; `ops-mirror` is read-only. For behavior conflicts trust loaded production revision, then reconcile main.” Routes “which copy is real?”. Invalidated by ownership or deployment topology changes.

## `architecture`

**Bad:** “The system has an API, database, and worker.” It is a generic noun list.

**Good:** “HTTP handlers validate and enqueue immutable order commands; the worker alone owns order-state transitions; PostgreSQL is authoritative for state, while Redis only deduplicates submissions. The API never marks fulfillment complete.” Routes component ownership and dependency questions. Invalidated by ownership or dependency-direction changes.

## `flow`

**Bad:** “`submit()` calls `validate()`, then `save()`.” It omits lifecycle outcomes.

**Good:** “`POST /orders` validates, writes `pending`, and emits `OrderQueued` in one transaction. Workers claim by idempotency key, transition to `accepted|rejected`, retry transport failures three times, and leave business rejection terminal. Clients poll the persisted state.” Routes success, failure, retry, and terminal-state questions. Invalidated by state machine or delivery changes.

## `contract`

**Bad:** “The SDK exposes `resize()`.” It states neither promise nor failure.

**Good:** “`resize(Image, Size) -> Image` preserves color profile, rejects non-positive dimensions with `InvalidSize`, never mutates input, and remains source-compatible across 2.x. GPU acceleration is an implementation detail.” Routes public API and compatibility questions. Invalidated by signature, error, or version-policy changes.

## `domain`

**Bad:** “Orders have statuses.” It defines nothing.

**Good:** “An Order is the merchant intent; a Shipment is a fulfillment attempt. `cancelled` is terminal for Order, while a failed Shipment may be replaced. Payment authorization is evidence, not order acceptance.” Routes terminology and state-rule questions. Invalidated by entity or business-rule changes.

## `data`

**Bad:** “Data is stored in Postgres.” It omits ownership and migration.

**Good:** “`orders` owns current state; `order_events` is append-only audit lineage; migration `0042` backfills `merchant_ref` before the NOT NULL gate. Redis keys are disposable and rebuilt. Customer addresses are encrypted and excluded from debug export.” Routes schema, recovery, and sensitivity questions. Invalidated by schema, retention, or migration changes.

## `boundary`

**Bad:** “Keep the system secure.” It is not actionable.

**Good:** “Never execute fulfillment before persisted authorization; signature failure is fail-closed; production replay requires operator approval; the duplicate event table is retained for rollback compatibility.” Routes authorization and invariants. Invalidated by security policy or compatibility changes.

## `operations`

**Bad:** “Run Docker and check logs if it fails.” It lacks a health contract.

**Good:** “Start with `docker compose up api worker db`; healthy means `/health/ready=200`, worker heartbeat under 30s, and migration head matches binary revision. On queue stall check DB locks before restarting; replay remains manual.” Routes start, diagnosis, and recovery. Invalidated by runbook or health-signal changes.

## `verification`

**Bad:** “All tests must pass.” It overclaims.

**Good:** “Unit tests prove state transitions; contract tests prove HTTP errors; the three-order smoke proves API→DB→worker on PostgreSQL. SQLite tests do not prove locking behavior. PASS requires all three, BLOCKED means PostgreSQL unavailable.” Routes evidence and gate questions. Invalidated by test scope or acceptance changes.

## `build_release`

**Bad:** “Run build, then publish.” It omits artifact identity and gates.

**Good:** “`python -m build` consumes tagged source; wheel contents and SBOM are verified before signing. Version comes from the tag. Publish requires compatibility matrix green; rollback yanks the release and restores the prior deployment, never retags.” Routes packaging and release questions. Invalidated by toolchain, signing, or policy changes.

## `handoff`

**Bad:** “Continue fixing tests tomorrow.” It cannot be resumed.

**Good:** “Work stopped after migration `0042`; rollback test still fails on duplicate merchant refs. Next run `pytest tests/migrations/test_0042.py -k rollback`; do not rewrite the forward migration. Record the result here.” Routes blocker and next action. Invalidated as soon as work advances.

## `decision`

**Bad:** “We chose Postgres because it is reliable.” It omits alternatives and reevaluation.

**Good:** “Choose PostgreSQL advisory locks over Redis leases because transaction ownership must survive worker restart. Alternatives were lease renewal and single-worker serialization. Reevaluate if commands move outside PostgreSQL transactions.” Routes design rationale. Invalidated only when assumptions change.

## `incident`

**Bad:** “Queue broke; restarted worker; fixed.” It teaches nothing.

**Good:** “Symptom: accepted orders stopped progressing while health stayed green. Root cause: heartbeat checked process life, not claim age. Restart temporarily cleared locks; the durable fix added oldest-claim age to readiness. Do not begin with queue deletion.” Routes recurrence diagnosis. Invalidated when prevention or root cause is superseded.

## `history`

**Bad:** A mixed timeline that also claims the current deployment path.

**Good:** “v1 performed fulfillment inline; v2 introduced queued commands after timeout incidents; v3 made order events append-only for replay. Current behavior lives in architecture/flow Stages.” Routes evolution without competing with current truth. Invalidated only by historical correction.

## `generated_inventory`

**Bad:** A manually edited dependency list that silently drifts.

**Good:** “Generated by `turritopsis maintain`: deployment `7f12`, schema `0042`, SDK `2.6.1`, SBOM SHA-256 `…`. Overwrite on every verified release; do not hand-edit.” Routes exact mechanical state. Invalidated on regeneration.
