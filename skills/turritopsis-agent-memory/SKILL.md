---
name: turritopsis-agent-memory
description: Design, review, or repair Turritopsis Stages for Agent memory systems, shared project memory, long-term recall, evidence ingestion, retrieval indexes, corrections, retention, and memory maintenance. Use when a project stores knowledge across sessions or agents and must keep raw evidence, canonical truth, summaries, and rebuildable retrieval layers distinct.
---

# Turritopsis Agent Memory

Design memory as governed knowledge, not as a chat archive.

1. Use `$turritopsis-onboarding` for the local scan and validated skeleton workflow.
2. Read [stage-suite.md](references/stage-suite.md) before classifying this project.
3. Select only the responsibilities the implementation actually has. Rename Currents for the project; never copy the fixture mechanically.
4. Give raw evidence, accepted knowledge, episodic history, summaries, and retrieval indexes separate Authority.
5. Treat embeddings, caches, and search indexes as rebuildable generated data unless the project explicitly makes them canonical.
6. Record correction, deletion, retention, and provenance behavior as first-class contracts.
7. Leave unsupported beliefs unknown. Do not promote fluent inference into remembered fact.
8. Use [fixture.json](references/fixture.json) only as a quality example.

When filling bodies, answer the retrieval question first, cite real evidence, and add update triggers for schema, ingestion, ranking, retention, and correction changes.
