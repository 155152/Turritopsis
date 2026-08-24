# Human-facing PWA Stage suite

Use this suite when a web or installed PWA is how a person talks to an Agent, controls a service, reviews knowledge, or performs daily work.

## Core responsibilities

- `orientation` — Define the person's primary tasks, supported devices, starting route, and what remains outside the web surface.
- `authority` — State which backend API or durable store owns each fact and which browser values are cache, draft, optimistic state, or presentation only.
- `architecture` — Map shell, routes, state ownership, API client, local persistence, service worker, and notification or deep-link boundaries.
- `flow` — Give complete paths such as submit-to-confirmation, reply-to-render, offline-to-reconnect, notification-to-destination, and update-to-active-assets.
- `contract` — Define visible success, error, retry, cancellation, duplicate protection, loading, empty state, and accessibility behavior.
- `data` — Explain local storage, cache, synchronization, sensitive browser data, expiration, and server reconciliation.
- `boundary` — Cover authentication, private content, browser exposure, destructive action confirmation, cross-origin behavior, and fail-closed states.
- `operations` — Document asset publication, cache/version changes, rollback, health checks, and how to prove the exact route is current.
- `verification` — Include real viewport, keyboard, touch, installed-mode, offline, reconnect, stale-cache, and slow-network checks.
- `incident` — Preserve failures such as stale service workers, duplicate sends, rendering/storage confusion, and frontend limits that lacked server enforcement.
- `handoff` — Keep the active UX gap, affected route, last verified build, and smallest next test current.

## Judgment rules

- The UI is not automatically the source of truth. A disabled button may mirror a server limit but cannot enforce it alone.
- Stored content and rendered presentation are different responsibilities. One stored reply may render as several bubbles without changing message history.
- Write one Stage per human outcome or end-to-end path, not one per React component, CSS file, or route module.
- A global version string does not prove that one route, service-worker cache, or installed client is fresh. Name exact assets and verification evidence.
- Optimistic UI must describe reconciliation and failure. “The click worked” is not a completed flow.
- Offline is a product state, not merely a network exception. State what remains readable, queueable, retryable, or forbidden.
- Verify the result the person sees. Include supported viewport dimensions or device classes, focus order, and update/reconnect behavior.
- Keep private message bodies out of diagnostics when timing, metadata, or health evidence can answer the question.

## Common bad shapes

- `frontend.components` lists files but cannot answer how a message reaches durable storage.
- `ui.current` mixes deployed assets, product meaning, cache incidents, and current handoff.
- Button disabling is described as the authoritative quota or permission boundary.
- A service worker was bumped, so every device is declared updated without a real-client check.
- Rendering changes rewrite stored content because display and persistence were not separated.

## Strong Stage body

Start with what the person experiences and what proves completion. Then trace the owning API or store, client transitions, failure and retry states, privacy boundaries, and exact verification path. Add triggers for route, schema, state-owner, cache, authentication, or deployment changes.
