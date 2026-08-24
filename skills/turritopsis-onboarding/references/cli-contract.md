# Cold-start CLI contract

Use this contract instead of reading `turritopsis` package source. The CLI is a
complete cold-start path.

## Skeleton JSON

```json
{
  "title": "Project title",
  "subtitle": "Shared project truth",
  "classification_provenance": {
    "source": "installed-agent",
    "agent_self_reported": "codex",
    "created_at": "2026-08-24T00:00:00Z",
    "notes": "optional"
  },
  "currents": [
    {
      "id": "delivery",
      "name": "Delivery",
      "blurb": "How a change becomes a release",
      "stages": [
        {
          "id": "delivery.release_flow",
          "title": "How a change becomes a release",
          "type": "flow",
          "freshness": "steady",
          "purpose": "Route release lifecycle questions.",
          "search_hints": "release build publish rollback",
          "authority": "Current release lifecycle; excludes historical incidents.",
          "evidence_paths": ["README.md"],
          "update_triggers": ["The build or publish path changes"]
        }
      ]
    }
  ]
}
```

`title`, `subtitle`, and provenance `notes` are optional. All other shown fields
are required. `agent_self_reported` is untrusted diagnostic free text, not verified
provider/model identity. Current ids use lowercase letters, digits, `_`, or `-`;
Stage ids begin with their Current id plus `.`. Evidence paths must already appear
in `scan-evidence.json`.

Allowed Stage types are `orientation`, `authority`, `architecture`, `flow`,
`contract`, `domain`, `data`, `boundary`, `operations`, `verification`,
`build_release`, `handoff`, `decision`, `incident`, `history`, and
`generated_inventory`. Freshness is `volatile`, `steady`, `historical`, or
`generated`.

## Stage body Markdown

`apply-skeleton` creates this placeholder shape, and `get-stage --all` returns it.
Replace the placeholders with evidence-backed content while retaining the routing
metadata needed by search:

```markdown
# How a change becomes a release

Type: flow
Purpose: Route release lifecycle questions.
Search hints: release build publish rollback
Summary: Give the direct current answer here.
Verified: 2026-08-24 by codex from repository evidence
Status: current
Authority: Current release lifecycle; excludes historical incidents.
Freshness: steady

## Knowledge

Write the complete answer.

## Evidence

- `README.md` — release section

## Unknowns

- Preserve anything not yet confirmed.

## Update triggers

- The build or publish path changes.
```

The body is one complete knowledge region, not a JSON serialization and not one
file per source. `Summary`, Authority, evidence, unknowns, and update triggers must
agree with the Stage responsibility declared in the skeleton.

## Read revisions once

After applying the skeleton, retrieve every placeholder and body-hash revision in
one command:

```bash
turritopsis get-stage --all
```

Use the returned `revision` values as optimistic-concurrency preconditions. Do not
calculate hashes or inspect `revisions.py`.

## Batch body manifest

Write one UTF-8 Markdown file per Stage, then create a manifest beside the body
directory. Relative `body_file` paths resolve from the manifest directory.

```json
{
  "updates": [
    {
      "stage_id": "delivery.release_flow",
      "body_file": "bodies/delivery.release_flow.md",
      "expected_revision": "revision returned by get-stage --all",
      "mode": "replace"
    }
  ]
}
```

Run:

```bash
turritopsis update-stages --manifest updates.json --actor codex
```

`mode` is optional and defaults to `replace`; the other fields are required. The
command checks every Stage and revision before one atomic write. An unknown Stage,
invalid mode, missing body file, duplicate Stage, or stale revision applies none of
the batch. A revision conflict prints the affected Stage and current revision.
