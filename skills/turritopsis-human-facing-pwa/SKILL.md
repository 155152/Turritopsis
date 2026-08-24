---
name: turritopsis-human-facing-pwa
description: Design, review, or repair Turritopsis Stages for a PWA or web interface that is a person's first-class entry into an Agent or service. Use for interaction contracts, source-of-truth boundaries, browser state, offline and retry behavior, service-worker caches, responsive verification, privacy, deployment, and the distinction between stored data and rendered experience.
---

# Turritopsis Human-facing PWA

Map the PWA as a real product surface, not a decorative dashboard.

1. Use `$turritopsis-onboarding` for local scanning and skeleton application.
2. Read [stage-suite.md](references/stage-suite.md).
3. Choose Stages around human tasks and complete interaction paths, not component directories.
4. Identify the authority for each visible value. Separate backend truth, client state, cache, and rendered presentation.
5. Record offline, retry, duplicate-submit, authentication, privacy, update, and rollback semantics.
6. Treat service-worker and asset versions as route-specific operational evidence, not proof that every client updated.
7. Verify real installed and browser behavior at supported viewports; source inspection alone is insufficient.
8. Use [fixture.json](references/fixture.json) as a quality example, not a template.
