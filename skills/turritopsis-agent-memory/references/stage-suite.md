# Agent memory Stage suite

Use this suite for personal memory, project memory shared by several agents, retrieval-assisted assistants, and systems that turn observations into durable knowledge. It is a recommendation, not a fixed taxonomy.

## Core responsibilities

- `orientation` — Explain what the memory helps an Agent remember, who it serves, and what it deliberately does not store.
- `authority` — Name the source of truth for observations, accepted facts, human corrections, summaries, and indexes. State which layer wins on conflict.
- `architecture` — Map ingestion, adjudication, canonical storage, retrieval, maintenance, and export. Describe ownership, not a file tree.
- `flow` — Separate the write path from the recall path. Include rejection, correction, deletion, and stale-result behavior.
- `contract` — Define read, write, update, delete, provenance, confidence, and conflict semantics exposed to agents or tools.
- `data` — Describe record identity, provenance, retention, tombstones, sensitive fields, backups, and index rebuild inputs.
- `boundary` — State what must not become memory: unsupported inference, secrets outside scope, another person's private data, or raw conversations retained without a policy.
- `verification` — Cover retrieval relevance, false recall, stale correction, deletion propagation, rebuild equivalence, and cross-agent consistency.
- `operations` — Explain how to inspect drift, rebuild an index, repair failed ingestion, restore canonical data, and verify the result.
- `handoff` — Keep pending adjudications, known retrieval gaps, and the next maintenance action short and current.
- `generated_inventory` — Store index revision, embedding model, hashes, and counts only when generated deterministically.
- `decision`, `incident`, and `history` — Use for consequential memory-policy choices, failures worth preventing, and evolution that no longer describes current behavior.

## Judgment rules

- Raw evidence is not a belief. A transcript, event, or document may support canonical knowledge but does not become it automatically.
- A summary is not the source. Link it to the canonical Stage it compresses.
- An index is not the source. It should be replaceable without changing accepted knowledge.
- Current facts, preferences, episodes, decisions, and historical explanation have different lifetimes; separate them when their update triggers differ.
- One correction must propagate to every serving layer, including caches and retrieval indexes. Keep deletion and tombstone semantics explicit.
- Do not store entire chats merely because they are available. Record the durable fact, decision, or unresolved question with provenance.
- Measure false confident recall as well as missed recall. “Found something” is not retrieval success.
- Human correction outranks model inference. Intimacy, repetition, or confidence never creates Authority.

## Common bad shapes

- `memory.everything` mixes raw logs, current preferences, old incidents, and vectors.
- One Stage per conversation or source file makes retrieval mirror storage layout.
- “The model remembers the user” hides who accepted the fact, when it was verified, and how to remove it.
- Generated embeddings are edited by hand or treated as irrecoverable canonical data.
- Deleting canonical text leaves stale snippets searchable.

## Strong Stage body

Lead with the direct contract. Then name layers and ownership, cite paths plus schemas or symbols, list unknowns, and add concrete triggers such as a record schema change, a new ingestion source, a ranking-model change, or a retention-policy change.
