# Cold-start evaluation

Turritopsis was evaluated as a cold-start handoff layer on four third-party
open-source repositories that were not used to design their Stage maps. This page
records the useful evidence and the failures together; it is not a claim of universal
accuracy or a scale ceiling.

## Frozen setup

- Date: 2026-08-24 JST
- Turritopsis commit: `51e7c171bdb1f1c65d505fc88d77156276e5d77d`
- Agent: Pi 0.74.2 with `deepseek-v4-flash`
- One blank agent instance and the same one-sentence instruction per target
- Target repository, onboarding Skill, and Turritopsis virtual environment were the
  only visible inputs
- No retries were used to improve a result

The evaluation criteria were written before any run. They covered project-shaped Stage
design, evidence references, direct answers, preserved unknowns, retrieval, unique
authority, and the boundary between repository snapshots and live truth.

## Targets and results

| Target | Frozen commit | Language | LOC | Files | Currents / Stages | Wall time |
|---|---|---:|---:|---:|---:|---:|
| `sharkdp/fd` | `ee20f426ddf338ac7ead5c5f00ea49258005caaf` | Rust | 8,502 | 59 | 5 / 11 | 5m52s |
| `simonw/datasette` | `0337fba234bf574629d56be631468ea060495fa0` | Python | 81,218 | 328 | 8 / 14 | 5m30s |
| `atuinsh/atuin` | `824c8716d82bed774ee6a83c683087ae77715814` | Rust | 91,641 | 643 | 6 / 17 | 6m31s |
| `usebruno/bruno` | `203a622e1c00ed4df149d448729ab0e8a0c9e1a9` | JS/TS | 111,900 | 4,241 | 7 / 14 | 5m38s |

Across 293,261 lines and 5,271 files, the four runs took 23m31s and produced
56 Stages. All 56 contained the expected metadata structure, led with a direct
Summary, and preserved explicit unknowns.

The Stage bodies mentioned 351 path-like objects. Automated checks resolved 347 inside
their target repositories. Manual review classified the remaining four as two external
services, one HTTP route, and one user-side configuration filename rather than fabricated
repository paths. Two representative Stages were then checked claim by claim against
source; the other 54 received structural and reference validation, not exhaustive semantic
verification.

## What the evaluation found

### Fixed-capacity maps dilute as projects grow

The generated map remained roughly constant at 11–17 Stages while mapped source coverage
fell from 85.2% for `fd` to 8.5% for `bruno`. The useful early warning is therefore files
per Stage, not only lines of code: two files per Stage was detailed, 13–23 remained
comfortable, and 152 was a map rather than deep coverage.

### Retrieval initially ranked broad Stages too highly

On an eight-question preregistered routing set, the correct Stage was usually present in
the top three but appeared at top one only about three times. English function words and
long routing fields dominated the original weighted search. Later commits added English
stop-word handling and a regression suite; the frozen runs were not rewritten after that
fix.

### Code contributed facts that documentation did not promise

In the heavily documented Datasette target, a sampled permissions Stage surfaced source
facts such as `SkipPermissions`, a per-request `contextvar` cache, and
`DEFAULT_ALLOW_ACTIONS` that were absent from the documentation. These implementation
facts are precisely the kind of current project reality that a new coding agent otherwise
has to rediscover.

## Honesty boundary

- One model and one run were used per target; run-to-run variance is unknown.
- The repositories are public and may exist in model training data, so prior-knowledge
  contamination cannot be excluded.
- The evaluator was also the tool author. Preregistration reduces but does not remove that
  conflict.
- Audit tooling produced three false negatives during the experiment. Each rule was fixed
  and all four targets were re-audited with the same final version.
- Only two of 56 Stages received claim-by-claim semantic verification.
- The largest measured target was 111,900 LOC. This evaluation does not establish a maximum
  supported repository size.
- Snapshot evidence cannot prove live operational state. Volatile runtime claims still
  require a live check.

## Reproduction contract

Use the Turritopsis commit and target commits listed above. Start a blank agent with only
the repository, `skills/turritopsis-onboarding/`, and the installed CLI visible, then give
the same instruction:

```text
Cold start this repository with Turritopsis. The turritopsis CLI is on PATH and the
turritopsis-onboarding skill is loaded. Work in the current directory.
```

Preserve `scan-run.json`, `scan-evidence.json`, `scan-anomalies.json`, `stages.json`,
`changelog.jsonl`, the complete agent trace, exact model identity, and token accounting.
Do not compare only final prose: validate cited paths, routing order, unknowns, and
snapshot-versus-live claims.
