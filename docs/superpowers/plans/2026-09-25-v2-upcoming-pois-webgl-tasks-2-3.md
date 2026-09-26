# Tasks 2–3: Route-relative overview and visible-flow documentation

Companion to
[2026-09-25-v2-upcoming-pois-webgl](2026-09-25-v2-upcoming-pois-webgl.md).

## Task 2: Route-relative Overview POI eligibility

**Files:**

- Modify:
  `backend/starlink-location/app/services/overview_upcoming_pois.py:67-155`

- Modify: `backend/starlink-location/tests/unit/test_overview_upcoming_pois.py`
- Modify:
  `backend/starlink-location/tests/integration/test_overview_upcoming_pois.py`
  if the endpoint fixture owns the active-route contract

**Interfaces:**

- Consumes: `eta_results: dict[str, float | None]`, `flight_phase: str`,
  `current_progress: float | None`, and generated POI route projection.

- Produces: `OverviewUpcomingPoisResponse` whose `upcoming` is route-relative
  and whose `state` is `available` whenever an eligible POI exists.

- [ ] **Step 1: Write failing route-relative projection tests**

Add explicit tests:

```python
def test_in_flight_ahead_poi_is_upcoming_even_when_estimated_eta_is_negative():
    response = project_overview_upcoming_pois(
        pois=[poi("Ahead", "x_band_transition", 70)],
        eta_results={"ahead": -1.0},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )
    assert response.state == "available"
    assert response.pois[0].upcoming is True


def test_in_flight_behind_poi_is_not_upcoming_even_with_positive_eta():
    response = project_overview_upcoming_pois(
        pois=[poi("Behind", "x_band_transition", 20)],
        eta_results={"behind": 60.0},
        flight_phase="in_flight",
        current_progress=50,
        calculated_at=NOW,
    )
    assert response.state == "no_upcoming_pois"
    assert response.pois[0].upcoming is False
```

Also test anticipated historical POIs are available in route order and
post-arrival remains unavailable.

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_overview_upcoming_pois.py
```

Expected: the ahead negative-ETA test fails under the existing `eta_seconds >=
0` condition.

- [ ] **Step 3: Implement minimal route-relative eligibility**

Replace the in-flight eligibility branch with route-progress-only semantics:

```python
if flight_phase == "in_flight":
    upcoming = ahead_on_route
elif flight_phase == "post_arrival":
    upcoming = False
else:
    upcoming = True
```

Keep `eta_seconds`, `estimated_arrival_time`, `eta_type`, sorting, and
`map_retained` computation intact. Do not alter response models or client
filtering.

- [ ] **Step 4: Run unit and endpoint contract tests to verify GREEN**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_overview_upcoming_pois.py tests/integration/test_overview_upcoming_pois.py
```

Expected: all focused tests pass; if the integration file is absent, run the
endpoint test file identified by `rg 'overview/upcoming-pois' tests` and record
its exact path.

- [ ] **Step 5: Commit**

```bash
git add backend/starlink-location/app/services/overview_upcoming_pois.py backend/starlink-location/tests
git commit -m "fix(overview): make generated POIs route relative"
```

## Task 3: V2 visible-flow regression and documentation

**Files:**

- Modify: `tools/acceptance/journeys/v2-mission-retirement.mjs`
- Modify: `tools/tests/test_v2_acceptance_browser_contract.py`
- Modify: `docs/missions/v2-mission-retirement-acceptance.md`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**

- Consumes: real activated KML journey and `Upcoming POIs` accessible table.
- Produces: semantic V2 observation requiring KAAA/KBBB rows based on active
  route progress, while describing ETA as anticipated/estimated metadata rather
  than a wall-clock eligibility filter.

- [ ] **Step 1: Write failing adapter-contract tests**

Add executable/source-contract tests asserting the adapter requires route name,
KAAA, KBBB, and at least two POI rows after activation:

```python
def test_v2_adapter_requires_route_relative_generated_poi_rows():
    source = V2_ADAPTER.read_text()
    assert "V2 Acceptance Route KAAA-KBBB" in source
    assert "KAAA" in source
    assert "KBBB" in source
    assert "poiRows.count()) < 2" in source
```

Add a documentation test that says Upcoming POI visibility derives from
active-route position while ETA remains anticipated/estimated metadata.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest -q tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_docs.py
```

Expected: the new documentation contract fails before the wording is added.

- [ ] **Step 3: Update documentation and retain semantic adapter assertion**

Document the three ETA states exactly:

```markdown
Before planned departure, anticipated ETA is calendar-based. After a missed planned departure but before actual departure, planned route durations are re-anchored at now. Once in flight, ETA is estimated from the current route position; POI visibility remains route-relative.
```

Keep the adapter’s visible KAAA/KBBB/table-row assertion; do not introduce API
seeding, hidden navigation, or a synthetic clock.

- [ ] **Step 4: Run focused browser-contract/docs tests to verify GREEN**

Run:

```bash
python -m pytest -q tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_docs.py
node --check tools/acceptance/journeys/v2-mission-retirement.mjs
```

Expected: all focused tests and Node syntax check pass.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/journeys/v2-mission-retirement.mjs tools/tests/test_v2_acceptance_browser_contract.py tools/tests/test_acceptance_platform_docs.py docs/missions/v2-mission-retirement-acceptance.md docs/operations/acceptance-platform.md
git commit -m "docs(acceptance): describe route relative POIs"
```

[Return to the main plan](2026-09-25-v2-upcoming-pois-webgl.md).
