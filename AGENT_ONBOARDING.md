# Filling a scanned project

Turritopsis uses the currently installed Agent as the classifier and writer. It never needs a second LLM for cold start.

```bash
turritopsis scan
# Read .turritopsis/scan-run.json and scan-evidence.json.
# Use $turritopsis-onboarding to choose Stage types and a project suite.
# Write skeleton.json with classification provenance.
turritopsis apply-skeleton skeleton.json
```

The scan is local, deterministic, resumable, and complete before classification starts. `apply-skeleton` rejects invented evidence, invalid ids, empty responsibilities, duplicate Authority, garbage-drawer Stages, and excessive fragmentation.

Do not assume `anatomy`, `flow`, `bounds`, `manual`, or `genesis` fits every project. Read `skills/turritopsis-onboarding/references/stage-types.md` and `project-suites.md`, select the smallest useful set, and use the paired examples when a Stage is formatted correctly but says nothing.

After the skeleton is accepted, fill each Stage through `update_stage` with revision protection. Cite repository paths plus symbols, schemas, commands, or real artifacts. Preserve unknowns and conflicts; never convert a plausible inference or anomaly into canonical truth.
