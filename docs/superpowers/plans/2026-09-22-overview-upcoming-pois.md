<!-- markdownlint-disable MAX_LINES -->

# Overview Upcoming POIs Implementation Plan

<!-- markdownlint-disable-next-line MD013 -->
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

<!-- markdownlint-disable-next-line MD013 -->
**Goal:** Render retained mission-generated POIs on the `/overview` globe and a smooth, non-scrollable Top 5 upcoming-POI table driven by a truthful active-mission API.

<!-- markdownlint-disable-next-line MD013 -->
**Architecture:** Persist a typed `kind` and optional scheduled arrival timestamp on mission-generated POIs, then expose an active-mission projection from a new Overview router. For every request it uses the established dual-mode ETA service: schedule-derived anticipated ETA before departure and telemetry-position/current-speed/active-route-aware estimated ETA in flight. The React client projects the same API records into table and marker sets; one pure urgency utility supplies the marker halo and table-swatch colours from the returned dynamic estimated arrival. The current standalone route endpoint stars are removed in favour of the generated departure/arrival POIs.

<!-- markdownlint-disable-next-line MD013 -->
**Tech Stack:** Python 3.12 / FastAPI / Pydantic / pytest; React 19 / TypeScript / TanStack Query / React Three Fiber / Vitest / Playwright; Markdown.

**Spec:** `docs/superpowers/specs/2026-09-22-overview-upcoming-pois-design.md`

## Global Constraints

- Base the branch and PR on `dev`; target `dev`, never `main`.
- Preserve old POI JSON records: typed generated fields are optional and must
  not prevent loading old records.
- POI labels use identified imported departure/arrival waypoint names; use
  coordinate endpoint fallbacks only when no named semantic waypoint exists.
- Do not infer generated type from names, do not invent coordinates, default
  speeds, or arrival times, and do not claim estimates are telemetry.
- The table contains at most five rows and is never scrollable; its first visual
  swatch column has no header.
- Departure/arrival remain on the map for the active mission; other timed
  operational POIs expire 60 minutes after their current calculated arrival
  (anticipated before departure, route-aware estimated in flight); untimed
  operational POIs remain while the active mission/route context remains.
- In flight, derive every POI ETA on each endpoint request through the existing
  route-aware estimated calculator using current telemetry position, current
  speed, and active-route geometry; never subtract wall-clock time from
  `expected_arrival_time` .
  `estimated_arrival_time = calculated_at + eta_seconds` ; it is a model
  estimate, not telemetry.
- One frontend urgency projection controls both globe marker and table-swatch
  colours from `estimated_arrival_time` : green at >=60m, yellow-to-green over
  30–60m, red-to-yellow over 0–30m, red when overdue, slate when timing is
  unavailable. Scheduled `expected_arrival_time` is provenance only in flight.
- Use shared `StarMarker` , globe occlusion, and labels; no global bloom,
  additional marker renderer, Grafana changes, or fullscreen/navigation changes.
- Browser acceptance is exact-head Playwright at 1920x1080; frontend tests run
  with `NODE_ENV=test` because the host exports `NODE_ENV=production` .
- Documentation impact is in scope: update Overview user feature documentation
  and endpoint reference in the same PR.

## Review Focus

- An old persisted POI without `kind` or `expected_arrival_time` loads and is
  excluded from the Overview generated view rather than crashing or being
  misclassified.
- A route has no named departure/arrival waypoint: endpoint fallback exists
  once, but named imported endpoint labels are never replaced by generic
  Origin/Destination labels.
- A timed point is exactly at 30, 60, or 60-minutes-past arrival: colour and
  retention use inclusive, deterministic boundaries.
- A mission departs 30 minutes after schedule or its active route changes for a
  weather diversion: in-flight POI ETA, table order, marker colour, and expiry
  use current telemetry position/speed and changed active-route geometry, not
  the original timetable.
- More than five timed points and one untimed route-ahead point exist: the table
  remains five rows, with untimed entries only after all selected timed rows.
- An API request fails or there is no active mission: POIs disappear truthfully
  while aircraft, GEP, satellite, route, history, and canvas interaction remain
  intact.

---

## File Structure

<!-- markdownlint-disable MD060 -->
| File | Responsibility |
| --- | --- |
| `backend/starlink-location/app/models/poi.py` | Optional persisted generated-POI fields and response fields. |
| `backend/starlink-location/app/mission/timeline_builder/pois.py` | Idempotent creation/replacement of typed departure, arrival, AAR, X, and Ka POIs. |
| `backend/starlink-location/app/services/poi/manager.py` | Typed mission/leg deletion filter used during regeneration. |
| `backend/starlink-location/app/models/overview_upcoming_pois.py` | Narrow Pydantic API response types for the Overview. |
| `backend/starlink-location/app/services/overview_upcoming_pois.py` | Pure active-mission table/map projection and ordering/retention logic. |
| `backend/starlink-location/app/api/overview_upcoming_pois.py` | `GET /api/overview/upcoming-pois` dependency-bound router. |
| `backend/starlink-location/main.py` | Router registration only. |
| `frontend/mission-planner/src/services/overview-upcoming-pois.ts` | Same-origin typed API client. |
| `frontend/mission-planner/src/hooks/api/useOverviewUpcomingPois.ts` | Non-overlapping background query policy. |
| `frontend/mission-planner/src/pages/overview-upcoming-pois.ts` | Pure client projection: time parsing, retained markers, top-five rows, and urgency colour. |
| `frontend/mission-planner/src/pages/OverviewPoiMarker.tsx` | One labelled, occluded shared-star POI marker. |
| `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx` | Bounded table/state presentation only. |
| `frontend/mission-planner/src/pages/OverviewPage.tsx` | Connect API query to marker/panel; remove standalone endpoint stars. |
| `frontend/mission-planner/src/pages/OverviewPage.css` | Overlay and smooth bounded-table transition styles. |
| `frontend/mission-planner/tests/e2e/overview-globe.spec.ts` | 1920x1080 rendered contract. |
| `docs/features/overview.md`, `docs/api/endpoints/README.md`, `docs/api/endpoints/overview-upcoming-pois.md` | User and API documentation. |
<!-- markdownlint-enable MD060 -->

### Task 1: Persist and regenerate typed mission POIs

**Files:**

- Modify: `backend/starlink-location/app/models/poi.py`
- Modify: `backend/starlink-location/app/services/poi/manager.py`
- Modify: `backend/starlink-location/app/mission/timeline_builder/pois.py`
- Modify: `backend/starlink-location/app/mission/timeline_service.py`
- Modify: `backend/starlink-location/tests/unit/test_poi_manager.py`
- Modify: `backend/starlink-location/tests/unit/test_mission_timeline.py`
- Create: `backend/starlink-location/tests/unit/test_mission_generated_pois.py`

**Interfaces:**

<!-- markdownlint-disable-next-line MD013 -->
- Produces `MissionPoiKind = Literal['departure', 'arrival', 'aar_start', 'aar_end', 'x_band_transition', 'ka_coverage_exit', 'ka_coverage_entry', 'ka_transition']`.
- Adds optional `kind: MissionPoiKind | None` and
  `expected_arrival_time: datetime | None` to `POI` , `POICreate` , and
  `POIResponse` .
<!-- markdownlint-disable-next-line MD013 -->
- Produces `sync_mission_pois(mission, route, poi_manager, *, mission_start, mission_end, aar_windows, transition_schedule, coverage, parent_mission_id=None) -> None`.
<!-- markdownlint-disable-next-line MD013 -->
- Produces `POIManager.delete_leg_pois(route_id: str, mission_id: str, categories: set[str] | None = None, prefixes: Sequence[str] | None = None, kinds: set[MissionPoiKind] | None = None) -> int`.

- [ ] **Step 1: Write failing model and regeneration tests**

```python
# tests/unit/test_mission_generated_pois.py

def test_sync_mission_pois_keeps_imported_endpoint_labels_and_typed_schedule(
    mission, route, poi_manager, mission_window, aar_window, transition_schedule
):
    sync_mission_pois(
        mission, route, poi_manager,
        mission_start=mission_window.start,
        mission_end=mission_window.end,
        aar_windows=[aar_window],
        transition_schedule=transition_schedule,
        coverage=CoverageAnalysisResult(gaps=[], swaps=[]),
    )

    generated = {poi.kind: poi for poi in poi_manager.list_pois(mission_id=mission.id)}
    assert generated['departure'].name == 'KADW'
    assert generated['departure'].expected_arrival_time == mission_window.start
    assert generated['arrival'].name == 'RKSO'
    assert generated['arrival'].expected_arrival_time == mission_window.end
    assert generated['aar_start'].expected_arrival_time == aar_window.start_time
    assert generated['x_band_transition'].expected_arrival_time == transition_schedule[0][0]


def test_old_persisted_poi_without_generated_fields_loads(tmp_path):
    manager = POIManager(tmp_path / 'pois.json')
    manager._pois['legacy'] = POI(
        id='legacy', name='Legacy', latitude=0, longitude=0
    )
    manager._save_pois()
    reloaded = POIManager(tmp_path / 'pois.json')
    assert reloaded.get_poi('legacy').kind is None
    assert reloaded.get_poi('legacy').expected_arrival_time is None
```

- [ ] **Step 2: Run the focused tests and verify RED**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd backend/starlink-location && .venv/bin/pytest tests/unit/test_mission_generated_pois.py tests/unit/test_poi_manager.py -q`

<!-- markdownlint-disable-next-line MD013 -->
Expected: FAIL because `POI.kind`, `POI.expected_arrival_time`, and `sync_mission_pois` do not exist.

- [ ] **Step 3: Add the minimal persisted model and typed replacement behaviour**

```python
# app/models/poi.py
MissionPoiKind = Literal[
    'departure', 'arrival', 'aar_start', 'aar_end',
    'x_band_transition', 'ka_coverage_exit',
    'ka_coverage_entry', 'ka_transition',
]

class POI(BaseModel):
    kind: MissionPoiKind | None = None
    expected_arrival_time: datetime | None = None
```

Create departure and arrival from `route.waypoints` where `role` is `departure`
/`arrival`; preserve `waypoint.name` when non-empty. If absent, use
`route.points[0]` /`route.points[-1]` with deterministic `Departure` /`Arrival`
fallback labels. Use each existing timeline source timestamp for AAR, X, and Ka
entries. Replace generated POIs via `kinds` , not prefix matching; leave
manually managed POIs untouched. Pass the resolved AAR windows, X transition
schedule, coverage result, and mission window from `build_mission_timeline` into
`sync_mission_pois` .

- [ ] **Step 4: Run focused tests and verify GREEN**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd backend/starlink-location && .venv/bin/pytest tests/unit/test_mission_generated_pois.py tests/unit/test_poi_manager.py tests/unit/test_mission_timeline.py -q`

<!-- markdownlint-disable-next-line MD013 -->
Expected: PASS, including repeated synchronization producing one record per generated kind/boundary rather than duplicates.

- [ ] **Step 5: Commit the independently reviewable backend generation slice**

```bash
git add backend/starlink-location/app/models/poi.py \
  backend/starlink-location/app/services/poi/manager.py \
  backend/starlink-location/app/mission/timeline_builder/pois.py \
  backend/starlink-location/app/mission/timeline_service.py \
  backend/starlink-location/tests/unit/test_poi_manager.py \
  backend/starlink-location/tests/unit/test_mission_timeline.py \
  backend/starlink-location/tests/unit/test_mission_generated_pois.py
git commit -m "feat(pois): generate typed mission POIs"
```

### Task 2: Expose truthful active-mission Overview POIs

**Files:**

- Create: `backend/starlink-location/app/models/overview_upcoming_pois.py`
- Create: `backend/starlink-location/app/services/overview_upcoming_pois.py`
- Create: `backend/starlink-location/app/api/overview_upcoming_pois.py`
- Modify: `backend/starlink-location/main.py`
- Create: `backend/starlink-location/tests/unit/test_overview_upcoming_pois.py`
- Create: `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py`

**Interfaces:**

- Produces `OverviewUpcomingPoi` , with `poi_id` , `name` , `kind` , `latitude`
  , `longitude` , `projected_route_progress` , `expected_arrival_time`
  (scheduled provenance), `eta_seconds` , `estimated_arrival_time` , `eta_type`
  , `flight_phase` , `upcoming` , and `map_retained` .
- Produces `OverviewUpcomingPoisResponse(state, calculated_at, pois)` where
  `state` is `available` , `no_active_route` , `no_generated_pois` ,
  `no_upcoming_pois` , or `unavailable` .
<!-- markdownlint-disable-next-line MD013 -->
- Produces `project_overview_upcoming_pois(*, pois, eta_results, flight_phase, current_progress, calculated_at) -> OverviewUpcomingPoisResponse`.
- Exposes `GET /api/overview/upcoming-pois` from `overview_upcoming_pois.router`.

- [ ] **Step 1: Write failing pure-projection and API contract tests**

```python
# tests/unit/test_overview_upcoming_pois.py

def test_in_flight_projection_keeps_departure_and_arrival_on_map_but_not_table():
    response = project_overview_upcoming_pois(
        pois=[departure_at(0), passed_x_at(20, now - timedelta(minutes=20)),
              expired_ka_at(30, now - timedelta(minutes=61)), arrival_at(100)],
        flight_phase='in_flight', current_progress=50, now=now,
    )
    assert [poi.kind for poi in response.pois if poi.upcoming] == ['arrival']
    assert [poi.kind for poi in response.pois if poi.map_retained] == [
        'departure', 'x_band_transition', 'arrival'
    ]


def test_upcoming_order_places_untimed_route_order_after_timed_entries():
    response = project_overview_upcoming_pois(
        pois=[timed('A', 20, 60), untimed('B', 30), timed('C', 40, 30)],
        flight_phase='in_flight', current_progress=0, now=now,
    )
    assert [poi.name for poi in response.top_five] == ['C', 'A', 'B']


def test_in_flight_eta_uses_live_estimate_not_scheduled_arrival():
    response = project_overview_upcoming_pois(
        pois=[timed('X transition', 30, scheduled_at=now + timedelta(minutes=5))],
        eta_results={'X transition': estimated_eta(seconds=90 * 60)},
        flight_phase='in_flight', current_progress=0, calculated_at=now,
    )
    poi = response.pois[0]
    assert poi.eta_seconds == 90 * 60
    assert poi.estimated_arrival_time == now + timedelta(minutes=90)
    assert poi.upcoming is True


def test_api_returns_no_active_route_without_fabricating_records(client):
    response = client.get('/api/overview/upcoming-pois')
    assert response.status_code == 200
    payload = response.json()
    assert payload['state'] == 'no_active_route'
    assert payload['pois'] == []
    assert payload['calculated_at'].endswith('+00:00')
```

- [ ] **Step 2: Run focused tests and verify RED**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd backend/starlink-location && .venv/bin/pytest tests/unit/test_overview_upcoming_pois.py tests/integration/test_overview_upcoming_pois_api.py -q`

Expected: FAIL because the projection module and route do not exist.

- [ ] **Step 3: Implement the narrow projection service and router**

```python
# app/services/overview_upcoming_pois.py
RETAINED_AFTER_EXPECTED_ARRIVAL = timedelta(minutes=60)


def is_map_retained(poi: OverviewUpcomingPoi, *, now: datetime, upcoming: bool) -> bool:
    if poi.kind in {'departure', 'arrival'}:
        return True
    if upcoming or poi.estimated_arrival_time is None:
        return True
    return now <= poi.estimated_arrival_time + RETAINED_AFTER_EXPECTED_ARRIVAL
```

<!-- markdownlint-disable-next-line MD013 -->
The router obtains the active mission ID through `app.mission.routes.get_active_mission_id`, the active route from `get_route_manager`, typed POIs from `get_poi_manager`, telemetry position/speed from the coordinator, and phase/progress from the existing flight-state/route ETA source. It calculates each generated POI through `ETACalculator._calculate_route_aware_eta_anticipated` before departure or `ETACalculator._calculate_route_aware_eta_estimated(latitude, longitude, poi, active_route, speed_knots)` in flight; only an uncalculable point remains without ETA. It must not call generic `/api/pois/etas` or use its coordinate/speed defaults. Invalid coordinates are excluded before response construction. The UTC `calculated_at` plus `eta_seconds` produces `estimated_arrival_time`. In flight it is this dynamic time—not `expected_arrival_time`—that drives upcoming, ordering, retention, and the API's displayed ETA. Add integration tests that (a) call the route-aware estimated path with the same scheduled POI but two current positions/speeds and assert changed ETAs, and (b) swap active-route geometry and assert the new route changes the ETA.

Register only
`app.include_router(overview_upcoming_pois.router, tags=['Overview POIs'])` in
`main.py` .

- [ ] **Step 4: Run focused tests and verify GREEN**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd backend/starlink-location && .venv/bin/pytest tests/unit/test_overview_upcoming_pois.py tests/integration/test_overview_upcoming_pois_api.py tests/integration/test_pois_quick_reference.py -q`

<!-- markdownlint-disable-next-line MD013 -->
Expected: PASS, including exact 60-minute retention based on dynamic in-flight estimated arrival, no-active-route response, no-generated-POI response, post-arrival empty table, a late departure/current-speed ETA independent of scheduled arrival, reroute-sensitive ETA, and no fabricated timing.

- [ ] **Step 5: Commit the API slice**

```bash
git add backend/starlink-location/app/models/overview_upcoming_pois.py \
  backend/starlink-location/app/services/overview_upcoming_pois.py \
  backend/starlink-location/app/api/overview_upcoming_pois.py \
  backend/starlink-location/main.py \
  backend/starlink-location/tests/unit/test_overview_upcoming_pois.py \
  backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py
git commit -m "feat(overview): expose upcoming mission POIs"
```

### Task 3: Add the typed client query and pure timing projection

**Files:**

- Create: `frontend/mission-planner/src/services/overview-upcoming-pois.ts`
- Create: `frontend/mission-planner/src/services/overview-upcoming-pois.test.ts`
- Create: `frontend/mission-planner/src/hooks/api/useOverviewUpcomingPois.ts`
- Create: `frontend/mission-planner/src/hooks/api/useOverviewUpcomingPois.test.ts`
- Create: `frontend/mission-planner/src/pages/overview-upcoming-pois.ts`
- Create: `frontend/mission-planner/src/pages/overview-upcoming-pois.test.ts`

**Interfaces:**

- Produces `overviewUpcomingPoisApi.get(): Promise<OverviewUpcomingPoisResponse>`.
- Produces `useOverviewUpcomingPois()` with `refetchInterval: 5_000` ,
  `refetchIntervalInBackground: true` , and `retry: false` .
- Produces `urgencyColor(estimatedArrivalTime: string | null, now: Date): string`.
<!-- markdownlint-disable-next-line MD013 -->
- Produces `overviewPoiView(records, now): { markers: OverviewUpcomingPoi[]; topFive: OverviewUpcomingPoi[] }`.

- [ ] **Step 1: Write failing service, hook, and projection tests**

```ts
it.each([
  [60 * 60 * 1000, '#22c55e'],
  [45 * 60 * 1000, '#8fd13a'],
  [30 * 60 * 1000, '#facc15'],
  [15 * 60 * 1000, '#f28b2d'],
  [0, '#ef4444'],
])('uses the approved colour interpolation at %i ms', (remaining, colour) => {
  expect(urgencyColor(new Date(now.valueOf() + remaining).toISOString(), now)).toBe(colour);
});

it('uses slate for unavailable timing and retains untimed operational markers', () => {
  const view = overviewPoiView([untimedXTransition], now);
  expect(urgencyColor(null, now)).toBe('#64748b');
  expect(view.markers).toEqual([untimedXTransition]);
});

it('uses only map-retained markers and five table-upcoming rows', () => {
  const view = overviewPoiView(mixedRecords, now);
  expect(view.markers.map(({ poi_id }) => poi_id)).toContain('passed-x');
  expect(view.topFive).toHaveLength(5);
});
```

- [ ] **Step 2: Run focused tests and verify RED**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd frontend/mission-planner && NODE_ENV=test npx vitest run src/services/overview-upcoming-pois.test.ts src/hooks/api/useOverviewUpcomingPois.test.ts src/pages/overview-upcoming-pois.test.ts`

Expected: FAIL because the service, hook, and projection exports do not exist.

- [ ] **Step 3: Implement the minimum typed client and shared projection**

```ts
export type OverviewPoiKind =
  | 'departure' | 'arrival' | 'aar_start' | 'aar_end'
  | 'x_band_transition' | 'ka_coverage_exit'
  | 'ka_coverage_entry' | 'ka_transition';

export interface OverviewUpcomingPoi {
  poi_id: string;
  name: string;
  kind: OverviewPoiKind;
  latitude: number;
  longitude: number;
  expected_arrival_time: string | null; // scheduled provenance
  eta_seconds: number | null;
  estimated_arrival_time: string | null;
  eta_type: 'anticipated' | 'estimated' | null;
  upcoming: boolean;
  map_retained: boolean;
}
```

Use `apiClient.get('/api/overview/upcoming-pois')` . Derive urgency and
displayed in-flight ETA from `estimated_arrival_time` and the existing
one-second `useCurrentTime` value; do not refetch every second. Preserve
`expected_arrival_time` only as scheduled provenance. Keep the exact returned
server order for timed and untimed table entries, then `slice(0, 5)` . Validate
finite latitude/longitude before producing marker records.

- [ ] **Step 4: Run focused tests and verify GREEN**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd frontend/mission-planner && NODE_ENV=test npx vitest run src/services/overview-upcoming-pois.test.ts src/hooks/api/useOverviewUpcomingPois.test.ts src/pages/overview-upcoming-pois.test.ts`

<!-- markdownlint-disable-next-line MD013 -->
Expected: PASS, including all red/yellow/green boundaries, overdue/slate values, selection order, and a single 5-second polling query.

- [ ] **Step 5: Commit the query and projection slice**

```bash
git add frontend/mission-planner/src/services/overview-upcoming-pois.ts \
  frontend/mission-planner/src/services/overview-upcoming-pois.test.ts \
  frontend/mission-planner/src/hooks/api/useOverviewUpcomingPois.ts \
  frontend/mission-planner/src/hooks/api/useOverviewUpcomingPois.test.ts \
  frontend/mission-planner/src/pages/overview-upcoming-pois.ts \
  frontend/mission-planner/src/pages/overview-upcoming-pois.test.ts
git commit -m "feat(overview): project upcoming POI timing"
```

### Task 4: Render retained stars and a smooth bounded table

**Files:**

- Create: `frontend/mission-planner/src/pages/OverviewPoiMarker.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPoiMarker.test.ts`
- Create: `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx`
- Create: `frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx`
- Modify: `frontend/mission-planner/src/pages/OverviewPage.tsx`
- Modify: `frontend/mission-planner/src/pages/OverviewPage.css`

**Interfaces:**

<!-- markdownlint-disable-next-line MD013 -->
- Produces `<OverviewPoiMarker poi={OverviewUpcomingPoi} color={string} globeOccluder={RefObject<THREE.Group>} />`.
<!-- markdownlint-disable-next-line MD013 -->
- Produces `<UpcomingPoisPanel state={OverviewUpcomingPoisState} pois={OverviewUpcomingPoi[]} currentTime={Date} />`.
- `OverviewPage` consumes `useOverviewUpcomingPois()` and `overviewPoiView()`.

- [ ] **Step 1: Write failing render and panel tests**

```tsx
it('renders one imported endpoint label through the shared star marker', () => {
  render(<OverviewPoiMarker poi={departurePoi} color="#22c55e" globeOccluder={occluder} />);
  expect(renderedStarMarker).toHaveBeenCalledWith(
    expect.objectContaining({ coordinate: { latitude: 38.85, longitude: -76.93 }, color: '#22c55e' }),
    undefined
  );
  expect(screen.getByText('KADW')).not.toBeNull();
});

it('has a headerless swatch column, no scrolling, and a five-row maximum', () => {
  render(<UpcomingPoisPanel state="available" pois={sixPois} currentTime={now} />);
  expect(screen.getAllByRole('row')).toHaveLength(6); // header plus 5 body rows
  expect(screen.queryByRole('columnheader', { name: /urgency/i })).toBeNull();
  expect(screen.getByLabelText('Upcoming POIs')).toHaveStyle({ overflowY: 'hidden' });
});

it('declares a height transition for changing table size', () => {
  render(<UpcomingPoisPanel state="available" pois={twoPois} currentTime={now} />);
  expect(screen.getByTestId('upcoming-pois-body').className).toContain('upcoming-pois__body');
});
```

- [ ] **Step 2: Run focused tests and verify RED**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd frontend/mission-planner && NODE_ENV=test npx vitest run src/pages/OverviewPoiMarker.test.ts src/pages/UpcomingPoisPanel.test.tsx`

Expected: FAIL because the marker and panel components do not exist.

- [ ] **Step 3: Implement marker, panel, Overview integration, and CSS**

```tsx
function OverviewPoiMarker({ poi, color, globeOccluder }: OverviewPoiMarkerProps) {
  const coordinate = { latitude: poi.latitude, longitude: poi.longitude };
  return <>
    <StarMarker coordinate={coordinate} color={color} size={0.1} />
    <Html occlude={[globeOccluder]} position={globePosition(poi.latitude, poi.longitude, ROUTE_OVERLAY_RADIUS)} zIndexRange={[0, 0]}>
      <span className="globe-marker-label">{poi.name}</span>
    </Html>
  </>;
}
```

Replace `RouteEndpoint` , `origin` , and `destination` use in `OverviewPage`
with `view.markers.map(...)` ; retain the route path itself. Place
`UpcomingPoisPanel` in a non-intercepting overlay region without covering the
fullscreen control or globe legend. Render the first table cell as a bare
`.upcoming-pois__swatch` span, with an empty header cell (`aria-hidden="true"`),
not an Urgency header.

```css
.upcoming-pois__body {
  overflow: hidden;
  transition: height 180ms ease, max-height 180ms ease, padding 180ms ease,
    opacity 150ms ease, border-color 180ms ease, background-color 180ms ease;
}
```

Use a row-count-derived explicit body height or measured `max-height` value so
the transition has numeric endpoints. Do not use `height: auto` as the only
changed value, and do not introduce scrollbars.

- [ ] **Step 4: Run focused tests and verify GREEN**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd frontend/mission-planner && NODE_ENV=test npx vitest run src/pages/OverviewPoiMarker.test.ts src/pages/UpcomingPoisPanel.test.tsx src/pages/overview-upcoming-pois.test.ts`

<!-- markdownlint-disable-next-line MD013 -->
Expected: PASS, including imported label, no duplicated endpoint marker source, headerless swatch, five-row cap, no vertical scrolling, and transition class contract.

- [ ] **Step 5: Commit the visual slice**

```bash
git add frontend/mission-planner/src/pages/OverviewPoiMarker.tsx \
  frontend/mission-planner/src/pages/OverviewPoiMarker.test.ts \
  frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx \
  frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx \
  frontend/mission-planner/src/pages/OverviewPage.tsx \
  frontend/mission-planner/src/pages/OverviewPage.css
git commit -m "feat(overview): render upcoming mission POIs"
```

### Task 5: Prove the rendered contract and document the endpoint

**Files:**

- Modify: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`
- Modify: `docs/features/overview.md`
- Modify: `docs/api/endpoints/README.md`
- Create: `docs/api/endpoints/overview-upcoming-pois.md`

**Interfaces:**

- E2E route mock returns an `OverviewUpcomingPoisResponse` at `**/api/overview/upcoming-pois`.
- Documentation identifies the endpoint, state values, retention/table
  distinction, and no-Grafana-change scope.

- [ ] **Step 1: Write the failing exact-viewport browser contract and docs assertions**

```ts
test.describe('Upcoming POIs overview', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test('renders retained stars and the five-row upcoming POI quick reference', async ({ page }) => {
    test.setTimeout(60_000);
    await page.route('**/api/overview/upcoming-pois', route => route.fulfill({ json: activeMissionPois }));
    await page.goto('/overview');

    await expect(page.getByText('KADW', { exact: true })).toBeVisible();
    await expect(page.getByText('RKSO', { exact: true })).toBeVisible();
    const panel = page.getByLabel('Upcoming POIs');
    await expect(panel.getByRole('row')).toHaveCount(6);
    await expect(panel.getByRole('columnheader', { name: /urgency/i })).toHaveCount(0);
    await expect(panel).toHaveCSS('overflow-y', 'hidden');
    expect(await page.locator('canvas').screenshot()).toMatchSnapshot('overview-upcoming-pois.png');
  });
});
```

- [ ] **Step 2: Run the targeted test and verify RED**

<!-- markdownlint-disable-next-line MD013 -->
Run: `cd frontend/mission-planner && NODE_ENV=test npx playwright test tests/e2e/overview-globe.spec.ts --grep "retained stars" --project=chromium`

<!-- markdownlint-disable-next-line MD013 -->
Expected: FAIL because the Overview does not yet call the new API or display its panel/labels.

- [ ] **Step 3: Complete docs and any narrowly necessary test harness updates**

Document `GET /api/overview/upcoming-pois` , response states, generated kinds,
anticipated/estimated timing semantics, table Top 5 selection, map retention,
and `ETA unavailable` . Add the endpoint to the endpoint index. Do not edit
Grafana provisioning or claim its retirement.

- [ ] **Step 4: Run browser, frontend, and backend verification**

Run:

```bash
cd frontend/mission-planner
NODE_ENV=test npm run lint
NODE_ENV=test npm run build
NODE_ENV=test npm run test:unit
NODE_ENV=test npx playwright test tests/e2e/overview-globe.spec.ts --project=chromium
cd ../../backend/starlink-location
.venv/bin/pytest -q
```

<!-- markdownlint-disable-next-line MD013 -->
Expected: all commands PASS; browser output includes a fresh 1920x1080 rendered screenshot assertion. Record any unrelated pre-existing failure verbatim rather than describing it as a pass.

- [ ] **Step 5: Commit documentation and acceptance evidence changes**

```bash
git add frontend/mission-planner/tests/e2e/overview-globe.spec.ts \
  docs/features/overview.md docs/api/endpoints/README.md \
  docs/api/endpoints/overview-upcoming-pois.md
git commit -m "docs(overview): describe upcoming POIs"
```

## Final Delivery Sequence

- [ ] Push the feature branch and verify
  `git ls-remote --heads origin refs/heads/feat/overview-upcoming-pois` equals
  local `HEAD` after every reviewable commit.
- [ ] Create one PR targeting `dev` with `Closes #149` , the spec/plan links,
  documentation impact, baseline caveat (`NODE_ENV=test`), and exact
  verification evidence.
- [ ] Run independent task review after each task, rework on the same branch
  where required, and run independent whole-branch review before merge.
- [ ] Inspect exact-head GitHub Actions results and use a 1920x1080 rendered
  browser acceptance run before claiming readiness.
- [ ] Merge only the independently reviewed, green PR into `dev` ; do not merge
  or release to `main` .
