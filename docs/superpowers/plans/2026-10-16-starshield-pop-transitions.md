# Starshield PoP Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add advisory PoP transition forecasts to mission planning, live
flight, simulation, and customer PDFs without changing transport availability.

**Revision status:** Subsequent user clarification supersedes the original
advisory-only outage rule. The linked spec now defines conditional full-window
planned call outages and concurrency-only X fallback. Tasks 1–6 have initial
implementations; Task 7 is paused. Review the revised written spec before
writing the implementation amendment and resuming qualification.

**Architecture:** A backend catalog and pure spherical geometry engine produce
crossing records. Existing timing adapters attach UTC estimates; a separate live
evaluator reconciles observations. Simulation derives synthetic observations
from position; all presentation consumes the shared advisory contract.

**Tech Stack:** Existing Python/Pydantic/FastAPI, React/TypeScript, Vitest,
Playwright, and HTML-to-PDF renderer. Use standard-library spherical
calculations; no additional runtime dependency is required.

**Spec:**
[Approved design](../specs/2026-10-16-starshield-pop-transition-design.md).

## Global Constraints

- Every transition remains visible; full-window planned call outages apply only
  where no usable alternative exists, as defined in the revised spec.
- Preserve measured physical transport states and default Starshield preference.
  X blocked solely by Starshield concurrency counts as a planned fallback;
  independent AR/geometry and other hard blocks still disqualify X.
- “Each planning window is fixed at estimated crossing time minus five minutes
  through plus five minutes.”
- “Timeline rows contain no added text labels for transition windows.”
- “An unchanged public IP retains its geolocation without an age-based expiry.”
- “No PoP management UI or automatic catalog mutation is included.”
- Seed Los Angeles, Ashburn, Dallas, Sydney, Frankfurt, and Tokyo; use city
  centers.
- Preserve exact UTC in canonical evidence and Eastern-time PDF table
  formatting.
- Enable automatically with Starshield; independent real outages still apply.
- Retain production IP-geolocation behavior; synthetic IP mapping is
  simulation-only.
- Execute in an isolated feature worktree based on current `origin/dev`; keep
  the primary checkout on `dev`. Integrate through a PR against `dev`.
- This planning PR is documentation only. Start implementation only after plan
  review and execution-method selection; consume the approved spec commit if its
  documentation PR has not yet merged.
- Every test/build command needs `timeout --kill-after=10s` and an explicit
  limit. Stop task-owned processes and Compose resources immediately after
  checks.

## Review Focus

1. Geolocation returns a nearby suburb or alternate spelling: only an explicit
   city/country alias identifies a catalog entry; do not invent a known PoP
   (Task 3).
2. The aircraft is stationary, off route, or a route contains repeated vertices:
   no division by zero, backward ETA, or invented live progression (Tasks 1–2).
3. Public IP changes but geolocation fails while old metrics remain cached: the
   old city cannot complete the new transition (Task 3).
4. Catalog changes during background PDF capture: publication must reject the
   obsolete revision rather than pair new markers with old evidence (Task 6).
5. A window overlaps SOF, an outage, or a DST clock change: keep canonical UTC,
   all impacts, service decisions, and existing PDF clock context (Tasks 5–6).

## File and contract map

Paths below use `B = backend/starlink-location`, `F = frontend/mission-planner`.
Resolve these prefixes to real paths when running commands or editing files.

Create `B/app/services/pop/` with `models.py`, `catalog.py`, `geometry.py`,
`forecast.py`, `live.py`, and `__init__.py`. Keep geographic calculation free of
network, global metrics, mission storage, and UI dependencies. Create
`B/app/simulation/pop.py` for synthetic observations and
`B/app/mission/pop_forecast.py` for timing/mission adapters.

Shared immutable contracts in `models.py`:

```text
PopSite(id: str, city: str, country: str, latitude: float, longitude: float, aliases: tuple[str, ...], source: str, coordinate_source: str)
```

- `PopCatalog(sites: tuple[PopSite, ...], fingerprint: str)`.
- `RouteVertex(latitude: float, longitude: float)`.

```text
PopCrossing(id: str, from_pop_id: str, to_pop_id: str, segment_index: int, fraction: float, latitude: float, longitude: float, distance_meters: float)
```

```text
PopTransition(crossing: PopCrossing, crossing_utc: datetime, window_start_utc: datetime, window_end_utc: datetime)
```

```text
PopForecast(revision: str, catalog_fingerprint: str, status: Literal['ready', 'disabled', 'unavailable', 'indeterminate'], reason: str | None, transitions: tuple[PopTransition, ...])
```

```text
PopObservation(ip: str | None, entry: GroundEntryPoint | None, status: Literal['known', 'unknown'], source: Literal['live', 'simulation'])
```

```text
PopLiveState(revision: str, completed_ids: frozenset[str], overdue_ids: frozenset[str], tracked_transitions: tuple[PopTransition, ...])
```

and

```text
PopLiveAdvisory(kind: Literal['window', 'overdue', 'mismatch', 'observation_unknown'], transition_id: str | None, observed_pop_id: str | None)
```

Serialize datetime fields as UTC ISO 8601. Expose additive `pop_forecast` on
`MissionLegTimeline` and additive `pop_forecast`, `pop_observation`, and
`pop_advisories` in `/api/status`. Default absent fields safely for old
persisted timelines and frontend fixtures. Keep all service-state fields
unchanged.

## Task 1: Configurable catalog and complete spherical crossings

**Files:** Create the service package's models/catalog/geometry modules,
`B/app/assets/starshield-pops.json`, `B/tests/unit/test_pop_catalog.py`, and
`B/tests/unit/test_pop_geometry.py`. Modify `B/app/models/config.py` and
`B/app/core/config.py` to support a catalog path, retaining a bundled default.

Geometry raises `PopGeometryError(reason: str)` on sustained ambiguity or
antipodal legs; the forecast adapter converts it to indeterminate status.

**Interfaces:** `load_catalog(path: Path) -> PopCatalog`;

```text
nearest_pop(latitude: float, longitude: float, catalog: PopCatalog, previous_id: str | None = None) -> str | None
```

```text
find_crossings(vertices: Sequence[RouteVertex], catalog: PopCatalog, revision: str) -> tuple[PopCrossing, ...]
```

- [ ] Write failing tests: six default IDs; invalid/duplicate IDs and
      coordinates reject the whole catalog; canonical field ordering does not
      change its digest; actual catalog edits do. `test_equatorial_boundary`
      uses sites at (0, −10) and (0, 10), a route (0, −5) to (0, 5), and asserts
      a crossing at fraction `0.5 ± 1e-8`, latitude/longitude `0 ± 1e-8`. Cover
      three regions in one leg, anti-meridian, tangent/no change, sustained tie,
      route re-entry, repeated vertices, single-site catalog, and deterministic
      simulation ties.
- [ ] From B, run

```text
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt pytest tests/unit/test_pop_catalog.py tests/unit/test_pop_geometry.py -q
```

Verify failures concern missing behavior.

- [ ] Implement validation and geometry. For each nondegenerate minor
      great-circle leg, express its unit position as
      `u*cos(theta) + v*sin(theta)`. Enumerate roots of
      `dot(position, site_i - site_j) = 0` for every site pair within the arc,
      add endpoints, sort/deduplicate, and evaluate nearest sites in every open
      interval. Emit only actual winner changes. This avoids missed short
      regions between equal coarse samples. Reject ambiguous antipodal legs as
      indeterminate; skip zero-length legs. Use angular tolerance `1e-10`
      radians and keep route distance consistent with the existing haversine
      radius. A tie returns None unless `previous_id` is tied; simulation
      initialization applies sorted-ID order.
- [ ] Populate city centers with a documented public coordinate reference and
      source the six identities to the operator's Starshield email. Do not
      invent IP ranges or copy private email content. Ensure the Docker image
      includes the bundled JSON under its existing application copy rules.
- [ ] Repeat the focused command; expect all tests to pass. Commit as
      `feat: add sourced PoP catalog and spherical boundary detection`.

## Task 2: Shared timed forecast and mission publication

**Files:** Create `B/app/services/pop/forecast.py`,
`B/app/mission/pop_forecast.py`, `B/tests/unit/test_pop_forecast.py`, and
`B/tests/unit/test_mission_pop_forecast.py`. Modify `B/app/mission/models.py`,
`timeline_preparation.py`, and `timeline_builder/calculator.py` only where
needed to expose existing timing data without duplicating its model.

**Interfaces:**

```text
build_forecast(crossings: Sequence[PopCrossing], timestamp_for_distance: Callable[[float], datetime], *, revision: str, catalog_fingerprint: str) -> PopForecast
```

. Mission adapter

```text
forecast_for_mission(route: ParsedRoute, projector: RouteTemporalProjector, catalog: PopCatalog, *, revision: str, starshield_enabled: bool) -> PopForecast
```

. Use the existing live ETA/progress projection to construct the live
distance/time callback; do not substitute planned timestamps for current ETA.

- [ ] Write failing assertions: crossing T yields exactly T−300 and T+300
      seconds; departure moves all bounds uniformly; interior route timing
      anchors remain effective; disabled returns no transitions; no crossing is
      ready/empty rather than unavailable. Invalid timing/route/catalog and
      sustained ambiguity return explicit status/reason. Test
      stationary/off-route live input using existing ETA validity behavior and
      an anti-meridian route with unequal segment durations.
- [ ] Run the two new files with Task 1's bounded uv/pytest invocation; expect
      red.
- [ ] Implement adapters and additive `MissionLegTimeline.pop_forecast`. Attach
      advisories after existing transport evaluation; do not feed them into
      `build_timeline_segments`, outage statistics, or X policy optimization.
      Generate revision-scoped occurrence IDs from route occurrence and catalog
      fingerprint. Keep full bounds even where flight bounds clip the displayed
      marker.
- [ ] Add a regression comparing transport states, statistics, and planning
      preference before/after forecasting, including a real Ka outage and X
      conflict. Revised planned call-outage metrics are defined separately in
      the subsequent spec amendment. Recompute after effective-route and timing
      revisions; discard obsolete results.
- [ ] Run focused tests plus `tests/unit/test_mission_timeline.py` and
      `tests/unit/test_dateline_timeline.py`; expect pass. Commit as
      `feat: publish timed PoP advisories alongside mission timelines`.

## Task 3: Observed PoP reconciliation and live status

**Files:** Create `B/app/services/pop/live.py` and
`B/tests/unit/test_pop_live.py`. Modify `B/app/services/ground_entry_point.py`,
`B/app/api/status.py`, and `B/main.py`. Extend
`B/tests/unit/test_ground_entry_point.py` and create
`B/tests/integration/test_pop_status.py`.

**Interfaces:** `GroundEntryPointResolver.observation() -> PopObservation`;

```text
match_observed_pop(observation: PopObservation, catalog: PopCatalog) -> str | None
```

```text
evaluate_live(forecast: PopForecast, observation: PopObservation, *, nearest_id: str | None, next_id: str | None, now: datetime, state: PopLiveState) -> tuple[PopLiveState, tuple[PopLiveAdvisory, ...]]
```

- [ ] Write failing tests for same-IP cache retention, new-IP lookup failure and
      retry, alternate city/country aliases, and an unrecognized suburb
      remaining unmatched. Assert `observation.status == 'unknown'` after new-IP
      lookup failure even if last-known display data exists. Network failure
      never creates an outage.
- [ ] Run the new live/status tests and existing ground-entry testsExpect red.
- [ ] Expose current observation separately from last-known resolver data;
      preserve per-IP caching. Normalize explicit city/country aliases without
      geography-based reassignment. Evaluate active windows, early B completion,
      overdue A, and unrelated observed C per the spec. A mismatch clears only
      on nearest/next match; unknown is distinct. State resets on route
      revision, seek, or mode change.
- [ ] Add lifecycle tests with T=12:00Z: early B at 11:50 clears this
      occurrence; A at 12:06 remains overdue; C is mismatch; nearest/next clears
      mismatch; unknown never completes. Add re-entry A→B→A→B, no-next-crossing,
      disabled, stale aircraft, and out-of-order revision cases. Wire additive
      status fields using the active effective route and existing ETA/freshness
      criteria; avoid blocking HTTP status on new external network calls.
- [ ] Repeat focused tests; expect pass, including unchanged existing
      health/state fields. Commit as
      `feat: reconcile live PoP observations with route advisories`.

## Tasks 4–7: Integration and acceptance

Continue with the
[integration companion](2026-10-16-starshield-pop-transitions-integration.md)
for simulation, planner/Overview, customer PDFs/cache, and production
acceptance. Those tasks are part of this plan and use the contracts above.

## Plan review and execution handoff

All approved spec sections map to Tasks 1–7. The Review Focus cases are assigned
to their owning tests. The shared model definitions above are authoritative for
neighboring task interfaces; do not create parallel frontend/geographic engines.

Recommended execution: subagent-driven, because geometry, live lifecycle,
simulation, and captured PDF partitions each warrant a separate implementation
and review gate before later integrations rely on them. Native execution is also
available if the user prefers one implementer and a final independent review.
Wait for the user's plan review and execution-method selection before starting.
