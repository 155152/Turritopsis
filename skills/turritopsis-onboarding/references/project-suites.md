# Project-suite selection

Suites are recommended combinations, not mandatory templates. Identify the project shape, combine suites for hybrids, and keep only types that answer real recurring questions.

## Web / SaaS

Use orientation, architecture, request flow, domain, data, external contracts, auth/security boundary, operations, verification, and handoff. Emphasize request chains, database migrations, third-party dependencies, and production diagnosis.

## Library / SDK / Framework

Use orientation, public contract, compatibility, architecture, extension points, build/package, verification matrix, migration, and release policy. Emphasize promises to callers and compatibility preservation, not service operation.

## Data / ML

Use data lineage, pipeline flow, feature/label contract, model boundary, evaluation, reproducibility, serving/inference, privacy/drift, and current experiment/operations. Separate data facts, experimental results, and hypotheses.

## Mobile / Desktop

Use navigation, state ownership, local data/offline behavior, platform integrations, network contracts, build/signing, distribution/update, crash diagnosis, and handoff. Emphasize lifecycle, permissions, offline state, and platform release chains.

## Infrastructure / Platform / DevOps

Use topology, authority/ownership, configuration/secrets, change flow, observability, incident response, backup/restore, capacity/cost, security boundaries, and current state. Keep declared configuration separate from observed runtime state.

## Embedded / IoT / Hardware

Use hardware topology, firmware architecture, wire/protocol contract, timing/concurrency, power/resource limits, calibration, flashing/update, safety/failure behavior, field diagnosis, and physical test fixtures. Compilation is not device acceptance; retain hardware evidence boundaries.

## Research / Spec / Protocol

Use problem statement, terminology, evidence base, competing approaches, experiment design, decisions, unresolved questions, reproducibility, conformance, and roadmap. Never merge proposals, experimental evidence, and normative specification into one status.

## Monorepo / Plugin ecosystem overlay

Add workspace map, ownership boundaries, shared contracts, dependency direction, plugin lifecycle, compatibility/versioning, build/test orchestration, coordinated release, integration failures, and handoff. Model cross-package relationships; do not create one Stage per package.
