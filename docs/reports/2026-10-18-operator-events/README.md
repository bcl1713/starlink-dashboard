# Operator events verification

Issue #368, epic #361; draft PR #379. All inputs are synthetic. These checks
establish software behavior, not aircraft readiness or physical sound delivery.

## Production acceptance

Candidate: `5d399811f40d107bf0088456a175518119519077`. Production backend and
frontend Dockerfiles, with Nginx serving the compiled application on ordinary
HTTP. Node 22.22.2. Exact image revisions, archive hash, results and cleanup are
recorded in [acceptance.json](acceptance.json).

Both browser scenarios passed: the existing Overview/display-settings workflow
and the unified event workflow. The latter covers ten-minute preparation,
overlapping requirements, rescheduling, cancellation, still-connected customers
with closed/missing conferences, hidden-tab delivery suppression, bounded
catch-up, two clients, one durable acknowledgment, lost-response retry after
reload, actual predictor replacement during acknowledgment, unavailable sources,
offline/reconnection, backend restart, same-browser cue reservation and editor
drafts across drawer use. Viewports: 1920×1080, 390×844 and 844×390. Browser
contexts used Honolulu/Tokyo time zones while event labels remained UTC.

- [Browser assertions](events-proof.json)
- [Existing display compatibility](displays-proof.json)
- [Desktop screenshot](events-1920x1080.png)
- [Portrait screenshot](events-390x844.png)
- [Landscape screenshot](events-844x390.png)

The synthetic adapter uses the actual #348 PoP predictor and existing capability
projector. Mission-basis tests verify the full-window sole-Starshield planning
outage, usable Ka fallback and coordinated concurrency-only X fallback. Separate
live-position ETA tests retain unknown continuity when matching evidence is
unavailable. Model generation replacement returns 409; unavailable evidence
returns 503. Ordinary unproven production publications remain advisories and do
not acquire synthetic authority.

Durability checks cover acknowledgment-only receipts, two command receipts with
one acknowledgment, unchanged operational revisions, backup/restore and crashes
immediately before/after commit. Physical read-only/full media probes and
existing restore/epoch recovery checks passed. The actual #349 lifecycle/export
probe verified unchanged telemetry ZIP bytes, semantic planning CSV content and
capture revisions; simulation export remained rejected. See
[export evidence](events-exports.json).

The ownership runner reports every process group reaped, listener removed,
containers/networks/private volumes gone, images removed and temporary source
archives removed. Raw command logs and ownership records are retained locally at
`/tmp/issue-368-events-5d399811`; only synthetic selected evidence is committed.

## Other verification

- Full backend with tracked runtime and GFS dependencies: 4,082 passed,
  20 skipped. After final refinements, all 342 Operator tests passed.
- Frontend under Node 22.22.2: 1,826 unit tests passed; lint and production build
  passed. Existing bundler warnings remain.
- Acceptance harness: 30 tests passed; final fixture adjustments: 21 passed.
- Black, Ruff, Prettier, ESLint, Markdownlint, documentation links and filename
  conventions passed. Static policy/documentation tests: 12 passed.
- Product-source CI run 39093228845: static and frontend gates passed; backend
  was pending when this report was prepared. Final-head status will be recorded
  before handoff. Independent whole-branch review identified four Important issues: LAN HTTP UUID support, fresh consistent topology captures, actual route geometry identity, and expiry of finished model windows. Their regression tests passed after fixes; full-suite and replacement production acceptance are pending.

Early acceptance attempts exposed fixture write locations, a legacy corruption
probe assuming one migration row, an inherited npm launcher option and a test
that incorrectly expected page-local journal drafts to persist reload. Each was
corrected before the passing run. No production permissions or journal draft
persistence were changed to satisfy the harness.

## Operational limits

Model input alignment and publication guards must be proven independently of
matching mission/leg identifiers. Ordinary current model publishers lack the
complete guard, so modeled acknowledgment and unproven-alignment automatic cues
fail closed. Scheduled operational record alerts remain available. Local audio
requires a gesture; vibration and foreground delivery remain device/browser
best-effort. No background, push, routing or export behavior is added.

See [operating and upgrade instructions](../../operations/operator-events.md)
and the [approved design](../../superpowers/specs/2026-10-18-operator-events-design.md).
