# V2 Upcoming POIs and WebGL Acceptance Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make V2 Upcoming POIs route-relative with truthful ETA clock semantics and enable certified WebGL2 in the profile-owned headed acceptance browser.

**Architecture:** The ETA projection layer distinguishes future planned departure, overdue pre-departure, and in-flight estimation; the Overview projection consumes ETA as metadata while using route progress for eligibility. Browser rendering remains platform-owned: a verified descriptor-bound Chrome launch receives only the approved ANGLE/SwiftShader flags and the neutral card proves WebGL2 before any final build.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, pytest, Chromium CDP, Xvfb, Node.js neutral card.

**Spec:** `docs/superpowers/specs/2026-09-25-v2-upcoming-pois-webgl-design.md`

## Global Constraints

- Upcoming POI eligibility is route-relative; stale calendar ETA must not hide an ahead active-route POI.
- Before expected departure, anticipated ETA follows the planned clock; after missed expected departure but before actual departure, anchor planned elapsed route duration at now.
- In flight, live and simulation ETA derives from current route position/progress and time-to-reach from now.
- Post-arrival has no upcoming POIs; invalid POI kind/coordinates remain excluded.
- Keep ETA metadata truthful; do not describe shifted anticipated ETA as telemetry.
- Browser authority remains external/profile-owned and descriptor-bound; callers/adapters cannot supply browser flags.
- Add exactly `--use-gl=angle` and `--use-angle=swiftshader`; never add `--enable-unsafe-swiftshader`, headless fallback, `--no-sandbox`, or device emulation.
- Neutral browser health/final preflight must fail closed unless WebGL2 exists, renderer identity is retained, and the page/visual viewport and decoded PNG are 1920×1080 at DPR1.
- Preserve existing 1200-second final build cap, 120-second no-build startup cap, 1800-second external monitor policy, final evidence authority, and browser cleanup rules.
- Documentation impact is in scope: update operator/browser acceptance and V2 acceptance documentation.

## Review Focus

- A route whose expected departure is one second in the future must use the calendar schedule, not a shifted baseline.
- A route whose expected departure is one second in the past but remains pre-departure must produce a positive planned-duration ETA from now, not `-1`.
- An in-flight POI behind current route progress must stay unavailable even if its estimated ETA is positive.
- Chromium launch arguments must be added only by the profile-owned launch path; caller-supplied session/origin/flags must remain unavailable.
- A browser with the approved flags but no actual WebGL2 context must block before Compose build and retain renderer/browser diagnostics.

---

### Task 1: Truthful ETA clock-domain calculation

**Files:**
- Modify: `backend/starlink-location/app/services/eta/projection.py:201-296`
- Modify: `backend/starlink-location/tests/unit/test_eta_projection.py`

**Interfaces:**
- Consumes: `ParsedRoute.timing_profile.departure_time`, route waypoint `expected_arrival_time`, `datetime.now(timezone.utc)`.
- Produces: `_calculate_route_aware_eta_anticipated(current_lat, current_lon, poi, active_route) -> float | None`, returning either a positive seconds-from-now ETA, `None` when timing cannot be established, or no historical negative sentinel solely because planned departure has elapsed.

- [ ] **Step 1: Write failing anticipated-ETA tests**

Add tests using a route with departure `2026-09-25T12:00:00Z` and waypoint arrival `2026-09-25T12:30:00Z`. Freeze the projection module clock with its established test seam so one test runs at `11:45Z` and another at `13:00Z`:

```python
def test_anticipated_eta_before_expected_departure_uses_calendar_delta(
    monkeypatch, calculator, route_with_timing, timed_poi
):
    monkeypatch.setattr(projection_module, "datetime", frozen_datetime("2026-09-25T11:45:00Z"))
    assert calculator._calculate_route_aware_eta_anticipated(
        40.0, -73.0, timed_poi, route_with_timing
    ) == 45 * 60


def test_anticipated_eta_after_missed_departure_reanchors_planned_duration_at_now(
    monkeypatch, calculator, route_with_timing, timed_poi
):
    monkeypatch.setattr(projection_module, "datetime", frozen_datetime("2026-09-25T13:00:00Z"))
    # Expected route duration from departure to waypoint is 30 minutes.
    assert calculator._calculate_route_aware_eta_anticipated(
        40.0, -73.0, timed_poi, route_with_timing
    ) == 30 * 60
```

Add a test for a waypoint with no timing that still returns `None`.

- [ ] **Step 2: Run the new tests to verify RED**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_eta_projection.py -k 'anticipated_eta_before_expected_departure or anticipated_eta_after_missed_departure'
```

Expected: the missed-departure test fails because current code returns `-1.0`.

- [ ] **Step 3: Implement the minimal re-anchored anticipated ETA**

In `_calculate_route_aware_eta_anticipated`, derive a helper from the matched waypoint:

```python
planned_duration = waypoint.expected_arrival_time - departure_time
if departure_time > current_time:
    return (waypoint.expected_arrival_time - current_time).total_seconds()
return planned_duration.total_seconds()
```

Apply the same helper for the name-matched waypoint and projected-waypoint-index path. Return `None` when required timing is absent or duration is negative. Retain exception handling and no coordinate fallback.

- [ ] **Step 4: Run ETA projection tests to verify GREEN**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_eta_projection.py
```

Expected: all ETA projection tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/starlink-location/app/services/eta/projection.py backend/starlink-location/tests/unit/test_eta_projection.py
git commit -m "fix(eta): reanchor missed predeparture schedules"
```

### Task 2: Route-relative Overview POI eligibility

**Files:**
- Modify: `backend/starlink-location/app/services/overview_upcoming_pois.py:67-155`
- Modify: `backend/starlink-location/tests/unit/test_overview_upcoming_pois.py`
- Modify: `backend/starlink-location/tests/integration/test_overview_upcoming_pois.py` if the endpoint fixture owns the active-route contract

**Interfaces:**
- Consumes: `eta_results: dict[str, float | None]`, `flight_phase: str`, `current_progress: float | None`, and generated POI route projection.
- Produces: `OverviewUpcomingPoisResponse` whose `upcoming` is route-relative and whose `state` is `available` whenever an eligible POI exists.

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

Also test anticipated historical POIs are available in route order and post-arrival remains unavailable.

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_overview_upcoming_pois.py
```

Expected: the ahead negative-ETA test fails under the existing `eta_seconds >= 0` condition.

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

Keep `eta_seconds`, `estimated_arrival_time`, `eta_type`, sorting, and `map_retained` computation intact. Do not alter response models or client filtering.

- [ ] **Step 4: Run unit and endpoint contract tests to verify GREEN**

Run:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_overview_upcoming_pois.py tests/integration/test_overview_upcoming_pois.py
```

Expected: all focused tests pass; if the integration file is absent, run the endpoint test file identified by `rg 'overview/upcoming-pois' tests` and record its exact path.

- [ ] **Step 5: Commit**

```bash
git add backend/starlink-location/app/services/overview_upcoming_pois.py backend/starlink-location/tests
git commit -m "fix(overview): make generated POIs route relative"
```

### Task 3: V2 visible-flow regression and documentation

**Files:**
- Modify: `tools/acceptance/journeys/v2-mission-retirement.mjs`
- Modify: `tools/tests/test_v2_acceptance_browser_contract.py`
- Modify: `docs/missions/v2-mission-retirement-acceptance.md`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**
- Consumes: real activated KML journey and `Upcoming POIs` accessible table.
- Produces: semantic V2 observation requiring KAAA/KBBB rows based on active route progress, while describing ETA as anticipated/estimated metadata rather than a wall-clock eligibility filter.

- [ ] **Step 1: Write failing adapter-contract tests**

Add executable/source-contract tests asserting the adapter requires route name, KAAA, KBBB, and at least two POI rows after activation:

```python
def test_v2_adapter_requires_route_relative_generated_poi_rows():
    source = V2_ADAPTER.read_text()
    assert "V2 Acceptance Route KAAA-KBBB" in source
    assert "KAAA" in source
    assert "KBBB" in source
    assert "poiRows.count()) < 2" in source
```

Add a documentation test that says Upcoming POI visibility derives from active-route position while ETA remains anticipated/estimated metadata.

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

Keep the adapter’s visible KAAA/KBBB/table-row assertion; do not introduce API seeding, hidden navigation, or a synthetic clock.

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

### Task 4: Profile-owned ANGLE/SwiftShader WebGL2 preflight

**Files:**
- Modify: `tools/acceptance/platform/browser_bundle.py:21-47`
- Modify: `tools/acceptance/platform/health.py:146-191, 410-430`
- Modify: `tools/acceptance/browser/v2-mission-retirement.mjs`
- Modify: `tools/tests/test_acceptance_platform_bundle.py`
- Modify: `tools/tests/test_acceptance_platform_health.py`
- Modify: `tools/tests/test_v2_acceptance_browser_contract.py`
- Modify: `docs/operations/acceptance-platform.md`

**Interfaces:**
- Consumes: descriptor-bound `BrowserLaunchSpec.start(*arguments)` and platform-owned health card output.
- Produces: final/health browser session launched with the two exact flags and a bounded `webgl2` result containing `renderer`, `vendor`, and `version`; failure blocks before Compose.

- [ ] **Step 1: Write failing browser-launch and neutral-card tests**

Add tests with a fake descriptor launcher and a health-card fixture:

```python
def test_platform_browser_launch_adds_only_certified_angle_swiftshader_flags(monkeypatch):
    launched_arguments: tuple[str, ...] = ()
    def capture_start(_: int, arguments: tuple[str, ...]):
        nonlocal launched_arguments
        launched_arguments = arguments
        return FakeProcess()
    monkeypatch.setattr(browser_bundle_module, "_start_descriptor", capture_start)
    BrowserLaunchSpec(os.open(fake_browser, os.O_RDONLY)).start("about:blank")
    assert launched_arguments[-3:] == (
        "--use-gl=angle",
        "--use-angle=swiftshader",
        "about:blank",
    )
    assert "--enable-unsafe-swiftshader" not in launched_arguments


def test_final_browser_session_rejects_neutral_card_without_webgl2(profile, tmp_path, executor):
    executor.run_card = lambda launch, root: HealthProbeResult(
        metrics=EXACT_VIEWPORT_METRICS, artifacts={}, webgl2=None
    )
    with pytest.raises(ValueError, match="WebGL2"):
        start_final_browser_session(profile, tmp_path, executor)
```

Add an executable card-contract test requiring `canvas.getContext('webgl2')` and nonempty renderer/vendor/version before the card reports success.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_v2_acceptance_browser_contract.py
```

Expected: launch-argument and missing-WebGL2 tests fail before the capability is implemented.

- [ ] **Step 3: Implement profile-owned flags and strict card data**

Extend only the platform launch authority so every browser launched from `start_final_browser_session` uses:

```python
"--use-gl=angle",
"--use-angle=swiftshader",
```

Do not allow the product contract, runner CLI, or adapter to supply flags. Extend the neutral card JSON with a bounded WebGL result:

```js
const canvas = document.createElement('canvas');
const gl = canvas.getContext('webgl2');
if (!gl) throw new Error('platform WebGL2 preflight failed');
const debug = gl.getExtension('WEBGL_debug_renderer_info');
const webgl2 = {
  renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
  vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
  version: gl.getParameter(gl.VERSION),
};
```

Validate nonempty string fields in Python before returning the session, retain the result in health/final browser evidence, and preserve all existing neutral viewport/raster validation.

- [ ] **Step 4: Run focused browser platform suite to verify GREEN**

Run:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_v2_acceptance_browser_contract.py
python -m compileall -q tools/acceptance/platform tools/tests
node --check tools/acceptance/browser/v2-mission-retirement.mjs
git diff --check
```

Expected: all focused tests, syntax, compilation, and whitespace checks pass.

- [ ] **Step 5: Commit**

```bash
git add tools/acceptance/platform/browser_bundle.py tools/acceptance/platform/health.py tools/acceptance/browser/v2-mission-retirement.mjs tools/tests docs/operations/acceptance-platform.md
git commit -m "fix(acceptance): certify WebGL2 browser capability"
```

## Final Verification

- [ ] Run the complete focused platform suite after all tasks:

```bash
PYTHONPATH=tools python -m pytest -q tools/tests/test_acceptance_platform_bundle.py tools/tests/test_acceptance_platform_health.py tools/tests/test_acceptance_platform_runner.py tools/tests/test_acceptance_platform_contracts.py tools/tests/test_acceptance_platform_docs.py tools/tests/test_v2_acceptance_browser_contract.py
```

- [ ] Run backend target verification from its project environment:

```bash
cd backend/starlink-location
.venv/bin/python -m pytest -q tests/unit/test_eta_projection.py tests/unit/test_overview_upcoming_pois.py
black --check app tests
ruff check app tests
```

- [ ] After independent task review and whole-branch review, push the exact SHA, run fresh health and static lanes, then issue exactly one authorized 1800-second final lane. Require sealed WebGL2 renderer identity, exact viewport/raster, visible KAAA/KBBB POI rows, image identity, checksums, and cleanup before any final claim.
