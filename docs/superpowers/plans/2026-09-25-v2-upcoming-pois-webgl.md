# V2 Upcoming POIs and WebGL Acceptance Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make V2 Upcoming POIs route-relative with truthful ETA clock semantics
and enable certified WebGL2 in the profile-owned headed acceptance browser.

**Architecture:** The ETA projection layer distinguishes future planned
departure, overdue pre-departure, and in-flight estimation; the Overview
projection consumes ETA as metadata while using route progress for eligibility.
Browser rendering remains platform-owned: a verified descriptor-bound Chrome
launch receives only the approved ANGLE/SwiftShader flags and the neutral card
proves WebGL2 before any final build.

**Tech Stack:** Python 3.11, FastAPI/Pydantic, pytest, Chromium CDP, Xvfb,
Node.js neutral card.

**Spec:** `docs/superpowers/specs/2026-09-25-v2-upcoming-pois-webgl-design.md`

## Global Constraints

- Upcoming POI eligibility is route-relative; stale calendar ETA must not hide
  an ahead active-route POI.

- Before expected departure, anticipated ETA follows the planned clock; after
  missed expected departure but before actual departure, anchor planned elapsed
  route duration at now.

- In flight, live and simulation ETA derives from current route
  position/progress and time-to-reach from now.

- Post-arrival has no upcoming POIs; invalid POI kind/coordinates remain
  excluded.

- Keep ETA metadata truthful; do not describe shifted anticipated ETA as
  telemetry.

- Browser authority remains external/profile-owned and descriptor-bound;
  callers/adapters cannot supply browser flags.

- Add exactly `--use-gl=angle` and `--use-angle=swiftshader`; never add
  `--enable-unsafe-swiftshader`, headless fallback, `--no-sandbox`, or device
  emulation.

- Neutral browser health/final preflight must fail closed unless WebGL2 exists,
  renderer identity is retained, and the page/visual viewport and decoded PNG
  are 1920×1080 at DPR1.

- Preserve existing 1200-second final build cap, 120-second no-build startup
  cap, 1800-second external monitor policy, final evidence authority, and
  browser cleanup rules.

- Documentation impact is in scope: update operator/browser acceptance and V2
  acceptance documentation.

## Review Focus

- A route whose expected departure is one second in the future must use the
  calendar schedule, not a shifted baseline.

- A route whose expected departure is one second in the past but remains
  pre-departure must produce a positive planned-duration ETA from now, not `-1`.

- An in-flight POI behind current route progress must stay unavailable even if
  its estimated ETA is positive.

- Chromium launch arguments must be added only by the profile-owned launch path;
  caller-supplied session/origin/flags must remain unavailable.

- A browser with the approved flags but no actual WebGL2 context must block
  before Compose build and retain renderer/browser diagnostics.

---

## Companion documents

- [Tasks 2–3: Route-relative overview and visible-flow
  documentation](2026-09-25-v2-upcoming-pois-webgl-tasks-2-3.md)

- [Task 4: Profile-owned ANGLE/SwiftShader WebGL2 preflight and final
  verification](2026-09-25-v2-upcoming-pois-webgl-task-4.md)

### Task 1: Truthful ETA clock-domain calculation

**Files:**

- Modify: `backend/starlink-location/app/services/eta/projection.py:201-296`
- Modify: `backend/starlink-location/tests/unit/test_eta_projection.py`

**Interfaces:**

- Consumes: `ParsedRoute.timing_profile.departure_time`, route waypoint
  `expected_arrival_time`, `datetime.now(timezone.utc)`.

- Produces: `_calculate_route_aware_eta_anticipated(current_lat, current_lon,
  poi, active_route) -> float | None`, returning either a positive
  seconds-from-now ETA, `None` when timing cannot be established, or no
  historical negative sentinel solely because planned departure has elapsed.

- [ ] **Step 1: Write failing anticipated-ETA tests**

Add tests using a route with departure `2026-09-25T12:00:00Z` and waypoint
arrival `2026-09-25T12:30:00Z`. Freeze the projection module clock with its
established test seam so one test runs at `11:45Z` and another at `13:00Z`:

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

In `_calculate_route_aware_eta_anticipated`, derive a helper from the matched
waypoint:

```python
planned_duration = waypoint.expected_arrival_time - departure_time
if departure_time > current_time:
    return (waypoint.expected_arrival_time - current_time).total_seconds()
return planned_duration.total_seconds()
```

Apply the same helper for the name-matched waypoint and projected-waypoint-index
path. Return `None` when required timing is absent or duration is negative.
Retain exception handling and no coordinate fallback.

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
