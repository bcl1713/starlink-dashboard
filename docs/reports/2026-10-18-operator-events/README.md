# Operator events verification

Issue #368, epic #361; draft PR #379. All inputs are synthetic. These checks
establish software behavior, not aircraft readiness or physical sound delivery.

Latest production modeled-alert qualification, review fixes and decisions are in
[the follow-up report](modeled-alerts.md). It supersedes the initial limitation
that withheld normal modeled cues.

## Initial production acceptance

Candidate: `7d0c61fde80a1dd541474d54a812ac4e98a932c8`. Production backend and
frontend Dockerfiles, with Nginx serving the compiled application on ordinary
HTTP. Node 22.22.2. Exact image revisions, archive hash, results and cleanup are
recorded in [acceptance.json](acceptance.json).

All three browser scenarios passed: the existing Overview/display-settings
workflow, the unified event workflow, and actual non-loopback HTTP with
secure-context UUID support absent. The unified workflow covers ten-minute
preparation, overlapping requirements, rescheduling, cancellation,
still-connected customers with closed/missing conferences, hidden-tab delivery
suppression, bounded catch-up, two clients, one durable acknowledgment,
lost-response retry after reload, actual predictor replacement during
acknowledgment, unavailable sources, offline/reconnection, backend restart,
same-browser cue reservation and editor drafts across drawer use. Viewports:
1920×1080, 390×844 and 844×390. Browser contexts used Honolulu/Tokyo time zones
while event labels remained UTC.

- [Browser assertions](events-proof.json)
- [Actual LAN HTTP assertions](events-lan-http.json)
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
`/tmp/issue-368-events-7d0c61fd`; only synthetic selected evidence is committed.

## Other verification

- Before final review refinements, the full backend with tracked runtime/GFS
  dependencies passed 4,082 tests, with 20 skipped; all 342 Operator tests
  passed. Review fixes then passed 32 focused backend tests plus a history-feed
  regression, with full backend rerun and final-head CI required for handoff.
- Final frontend under Node 22.22.2: 1,828 unit tests passed; lint and
  production build passed. Existing bundler warnings remain.
- Acceptance harness: 30 tests passed before review; 26 relevant harness tests
  passed after fixture/review refinements.
- Black, Ruff, Prettier, ESLint, Markdownlint, documentation links and filename
  conventions passed. Static policy/documentation tests: 12 passed.
- [Fresh whole-branch review and fixes](review.md): four Important findings
  fixed with regressions observed failing before correction. No findings were
  waived or deferred. [Execution rulings](decisions.md) record implementation
  choices and costs.
- Final-head static, backend and frontend gates are tracked in
  [PR #379 checks](https://github.com/bcl1713/starlink-dashboard/pull/379/checks).
  Evidence/documentation-only commits after the production candidate do not
  change the tested application or acceptance harness.

Early acceptance attempts exposed fixture write locations, a legacy corruption
probe assuming one migration row, an inherited npm launcher option and a test
that incorrectly expected page-local journal drafts to persist reload. Each was
corrected before the passing run. No production permissions or journal draft
persistence were changed to satisfy the harness.

## Operational limits

The initial delivery below used a synthetic participating adapter. Product
review 6248772010 correctly rejected withholding modeled cues from ordinary
valid inputs as completion. The subsequent production-source revisions reuse
captured mission preparation and the real #348 service through normal
application wiring. Their new qualification is documented in
[modeled alerts](modeled-alerts.md).

Local audio requires a gesture; vibration remains device/browser best-effort. No
background, push, routing or export behavior is added.

See [operating and upgrade instructions](../../operations/operator-events.md)
and the
[approved design](../../superpowers/specs/2026-10-18-operator-events-design.md).
