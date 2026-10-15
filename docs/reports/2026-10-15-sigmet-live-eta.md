# Live SIGMET crossing estimates

This follow-up replaces schedule-only crossing estimates during flight with
current UTC, route progress and measured speed. Before departure, planned
waypoint UTC remains authoritative. The flight display stays concise.

The current segment blends measured and planned speed; future segments use
planned speeds, sharing the route-aware POI speed rule. Valid timed points work
even when a KML title leaves optional summary metadata absent. Position and
speed must satisfy the existing freshness policy. Unavailable or ambiguous
current position produces unknown timing rather than a schedule fallback.
Completed crossings show passed; an occupied crossing retains its projected
exit. Published simulation replay uses mission time and occurrence-aware
progress, consistent with replay POIs. Advisory eligibility still uses actual
UTC. Geometry and acknowledgement identity remain unchanged.

## Validation

- Full scientific backend regression at product candidate `7bbce303`:
  3,352 passed / 20 skipped in 567.94 seconds; one existing Cartopy warning.
- Final concurrent-read admission, strict contracts, route context and optional
  service lifecycle at `04f88019`: 128 focused tests passed. Independent review
  confirmed materialized same-plan results keep their own ordering tokens and
  an internal selection epoch rejects observed static A-to-B-to-A changes.
- Frontend: 223 files / 1,641 tests passed with two workers; lint and production
  build passed. Frontend source is unchanged by the subsequent backend fixes.
- Acceptance-runner controls: 47 passed, including required live-state proof
  flags and replay-frame compatibility of the telemetry adapter.
- Canonical static checks passed on `04f88019`, including documentation links
  and typing policy.
- Exact `04f88019` production browser acceptance: all five scenarios passed
  in 4.0 minutes, with all fourteen encounter proof flags true.

The first unrestricted frontend run timed out loading the initial GFS switch in
`AviationSettingsCard.test.tsx` (“enabling winds atomically replaces its
counterpart and allows both off”). The full suite passed with bounded workers
without changing that component or its tests.

## Production evidence

Current exact candidate:

```text
04f88019cbb6a22c9f9f62b427706bbfcb74318e
```

Retained evidence is relative to the follow-up feature worktree:

```text
test-results/route-sigmets-0c218504cfb6/04f88019cbb6a22c9f9f62b427706bbfcb74318e/
```

The new controls deliberately place the stored schedule tomorrow while an
active aircraft is on today's route. Separate checks verify live overlap on
both screens, unknown timing for stale speed, and passed crossings after moving
the aircraft beyond the hazards. The scenario also retains positive, negative,
unknown, desktop/mobile, acknowledgement and selected-only controls.

Earlier run evidence and failure traces remain under `test-results/route-sigmets-*`.
They exposed automatic fixture departure during planned checks, a missing
replay keyword in the telemetry adapter, optional KML summary gating, a stale
selected-card locator, and a concurrent empty-response polling delay. These
were corrected with focused regressions and production reruns; none of those
failed runs is presented as passing evidence.

Follow-up logs, red/green controls, ownership records and host cleanup checks
remain under `test-results/sigmet-live-eta/`. Production acceptance uses synthetic
controls, pinned dated AWC replay and software WebGL; it does not establish
current upstream availability or target-workstation performance.

Final live state evidence records four overlapping notices, four unknown notices
with stale speed, and four passed notices after advancing beyond the hazards.
Expanded live Details and desktop/mobile screenshots were visually inspected.
The display retains crossing windows and operational bulletin information
without delivery or implementation metadata.

All six production projects have empty container, network, disposable-volume
and owned-process inventories. Ports are free and private source directories
removed. An approved host check independently confirmed those receipts and no
remaining worktree runtime workers. Task test-data directories and the temporary
dependency symlink were removed; shared dependencies and configuration remain.
The feature worktrees and evidence are retained for the open PR. Subsequent
documentation-only commits cite this candidate and claim no new image run.
