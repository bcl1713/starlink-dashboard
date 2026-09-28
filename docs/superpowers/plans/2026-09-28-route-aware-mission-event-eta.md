<!-- markdownlint-disable-file MAX_LINES -->
<!-- markdownlint-disable MD001 MD013 MD032 MD036 -->

# Route-Aware Mission-Event ETA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking. Brian explicitly selected native execution and prohibited subagent
> dispatch for this delivery.

**Goal:** Make Overview calculate truthful, route-segment-aware in-flight ETA
for generated off-route mission events with a valid stored projection.

**Architecture:** `POIManager` remains the route-projection producer.
`ETAProjection` consumes its persisted projection tuple as the authoritative
input, validates it, and walks active-route geometry to its interior projected
point. The Overview endpoint retains null timing for unsafe input; the existing
React panel distinguishes ordinary estimates from anticipated schedule timing.

**Tech Stack:** Python 3.11, FastAPI, Pydantic models, pytest, React/TypeScript,
Vitest, Playwright, npm, repository `tools/verify` static gate.

**Spec:** `docs/superpowers/specs/2026-09-28-route-aware-mission-event-eta-design.md`

## Global Constraints

- Preserve the `/api/overview/upcoming-pois` response shape and Mission V2
  persistence schema.
- Route-aware ETA uses the stored projected point, segment index, and progress;
  never re-projects it through a second tolerance search.
- In-flight failures remain null. Do not introduce direct-distance, endpoint
  coordinate, default-speed, or schedule fallback for generated mission events.
- The estimate is not telemetry or schedule truth.
- Current-segment speed is blended; later segments use planned speeds or the
  existing valid segment-speed fallback.
- Use deterministic simulated telemetry; no physical-aircraft dependency.
- Ordinary estimated UI rows show UTC only; anticipated rows retain
  `anticipated`.
- Documentation impact is limited to the Overview feature and Upcoming POIs API
  reference. No runbook, release-note, schema, Docker, or CI change is needed.
- Preserve 1920x1080 browser acceptance when the table wording changes.

## File Structure

- `backend/starlink-location/app/services/eta/projection.py` — validates stored
  projection tuple and calculates the route-segment ETA.
- `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py`
  — endpoint-level deterministic simulation regression contracts.
- `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx` — ETA label policy.
- `frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx` — panel copy
  regression contract.
- `frontend/mission-planner/tests/e2e/overview-globe.spec.ts` — 1920x1080
  browser table wording evidence.
- `docs/api/endpoints/overview-upcoming-pois.md` — endpoint timing provenance.
- `docs/features/overview.md` — user-facing Overview timing explanation.

## Review Focus

1. A valid projection whose destination is inside a segment must use only the
   segment prefix, not the full segment or the event's direct coordinate; Task 2
   pins this with a numerically distinct route-versus-direct ETA assertion.
2. A projection behind the current route point must not become a positive future
   ETA; Task 3 pins null timing and `no_upcoming_pois` behavior.
3. Non-finite/out-of-range projection and telemetry values must fail closed;
   Task 3 parameterizes malformed tuple cases.
4. Multi-segment travel must use current-speed blending only once and planned
   speeds afterwards; Task 2 asserts the calculated segment sum.
5. The table must not erase the anticipated qualifier while removing redundant
   ordinary `estimated`; Task 4 covers panel and exact viewport browser output.

---

### Task 1: Restore the auditable RED baseline

**Files:**

- Revert: commit `483acaf1d420f4a4ec6e139e81fd1030d3b76412` only.
- Preserve: `6f1de8cb93cc9276b3a59f8c8b70b794f10e4369` design specification.

**Interfaces:**

- Consumes: the pre-existing published candidate that was authored before the
  approved strict-TDD gate.
- Produces: a feature branch with the original `origin/dev` product behavior
  and the committed #177 specification retained.

- [ ] **Step 1: Verify the exact candidate commit is the only product change to remove**

Run:

```bash
git show --name-status --format=fuller 483acaf1
git diff --name-only 483acaf1^ 483acaf1
git status --short
git log --oneline origin/dev..HEAD
```

Expected: only the seven candidate product/docs/test files belong to
`483acaf1`; the design spec remains a separate later commit; the worktree is
clean.

- [ ] **Step 2: Revert the pre-TDD candidate without rewriting remote history**

Run:

```bash
git revert --no-edit 483acaf1d420f4a4ec6e139e81fd1030d3b76412
git show --stat --oneline HEAD
git diff --check origin/dev...HEAD
```

Expected: a normal feature-branch revert removes only the candidate behavior;
the specification remains present; no force push occurs.

- [ ] **Step 3: Prove the intended endpoint behavior is RED**

Temporarily create the Task 2 test below, then run:

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  -k 'interior_projected_mission_event' -q
```

Expected: FAIL because the restored ETA consumer tries a second
proximity/tolerance segment discovery and does not accept the valid stored
interior projection contract.

- [ ] **Step 4: Commit the recovery boundary**

```bash
git add -u
git commit -m "revert: reset unverified route ETA candidate"
```

Expected: the branch history makes the strict-TDD reset explicit and auditable.

### Task 2: Calculate a valid interior stored projection along the route

**Files:**

- Modify: `backend/starlink-location/app/services/eta/projection.py`.
- Modify: `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py`.

**Interfaces:**

- Consumes: `POI.projected_latitude`, `projected_longitude`,
  `projected_waypoint_index`, and `projected_route_progress`; live or simulated
  `latitude`, `longitude`, and `speed_knots`; `ParsedRoute.points` and expected
  segment speeds.
- Produces: a positive `eta_seconds` and `estimated_arrival_time` from
  `ETAProjection._calculate_off_route_eta_with_projection_estimated()` through
  `/api/overview/upcoming-pois`.

- [ ] **Step 1: Write the failing endpoint regression test**

Add this focused test shape beside the existing in-flight endpoint tests:

```python
def test_api_estimates_interior_projected_mission_event_from_route_progress(
    client, monkeypatch
):
    active_route = route([(40.0, -73.0), (40.0, -71.0)])
    event = scheduled_poi().model_copy(
        update={
            "id": "interior-projection",
            "latitude": 41.0,
            "longitude": -72.0,
            "projected_latitude": 40.0,
            "projected_longitude": -72.0,
            "projected_waypoint_index": 0,
            "projected_route_progress": 50.0,
        }
    )
    install_in_flight_simulated_telemetry(client, latitude=40.0, longitude=-73.0, speed=300)
    arrange_active_v2_context(client, active_route=active_route)
    override_generated_pois(client, [event])

    response = client.get("/api/overview/upcoming-pois")

    poi = response.json()["pois"][0]
    assert response.status_code == 200
    assert poi["eta_type"] == "estimated"
    assert poi["eta_seconds"] == pytest.approx(route_eta_to(40.0, -72.0, 300))
    assert poi["eta_seconds"] < direct_eta_to(41.0, -72.0, 300)
    assert poi["estimated_arrival_time"] is not None
```

Implement `install_in_flight_simulated_telemetry`, `override_generated_pois`,
`route_eta_to`, and `direct_eta_to` as local test helpers only if their existing
fixture equivalents cannot express the same setup. The test must exercise the
actual endpoint, not an implementation mock.

- [ ] **Step 2: Run the focused test to verify RED**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  -k 'interior_projected_mission_event' -q
```

Expected: FAIL with null/missing ETA under the restored implementation. Record
the failure output in the delivery report.

- [ ] **Step 3: Implement the minimum stored-tuple route walk**

In `_calculate_off_route_eta_with_projection_estimated()`:

```python
projection = (
    poi.projected_latitude,
    poi.projected_longitude,
    poi.projected_waypoint_index,
    poi.projected_route_progress,
)
if not _valid_projection_tuple(projection, active_route, speed):
    return None

for index in range(nearest_point_index, projection_segment_index + 1):
    start = active_route.points[index]
    end = (
        (projection_latitude, projection_longitude)
        if index == projection_segment_index
        else active_route.points[index + 1]
    )
    segment_speed = blended_speed if index == nearest_point_index else planned_speed
    total_seconds += distance(start, end) / 1852.0 / segment_speed * 3600.0
return total_seconds if total_seconds > 0 else None
```

Use the module's existing calculation and exception policy; keep validation
local/private unless a reusable helper is required for clarity. Delete the
second `_distance_to_line_segment` tolerance search. Do not alter the producer
or add a direct-coordinate fallback.

- [ ] **Step 4: Run the focused test to verify GREEN**

Run the exact command from Step 2.

Expected: PASS with a positive endpoint ETA matching the stored projected route
point and distinguishable from the off-route direct-coordinate ETA.

- [ ] **Step 5: Add the multi-segment speed policy regression**

Add an endpoint test using three route points, a stored projection in the final
segment, telemetry speed different from the first segment's planned speed, and
a second planned segment speed. Assert the ETA equals the sum of:

```python
first_distance_nm / ((telemetry_speed + first_planned_speed) / 2) * 3600
+ final_prefix_distance_nm / second_planned_speed * 3600
```

Run:

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  -k 'interior_projected_mission_event or projected_event_uses_segment_speeds' -q
```

Expected: PASS. This proves route timing semantics, not merely non-null output.

- [ ] **Step 6: Commit the route-aware ETA slice**

```bash
git add backend/starlink-location/app/services/eta/projection.py \
  backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py
git commit -m "fix(overview): calculate projected mission event ETA"
```

### Task 3: Fail closed for unsafe projections and simulation inputs

**Files:**

- Modify: `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py`.
- Modify: `backend/starlink-location/app/services/eta/projection.py` only if the
  Task 2 validation does not already make every case pass.

**Interfaces:**

- Consumes: the Task 2 stored-projection calculator and endpoint response
  projection.
- Produces: null `eta_seconds` and `estimated_arrival_time`, never a
  direct-distance substitute, for unsafe conditions.

- [ ] **Step 1: Write parameterized failing endpoint cases**

Add a parameterized test covering these modifications to an otherwise-valid
simulated in-flight event:

```python
@pytest.mark.parametrize(
    "projection_update",
    [
        {"projected_latitude": None},
        {"projected_longitude": float("nan")},
        {"projected_route_progress": 101.0},
        {"projected_waypoint_index": 99},
    ],
)
def test_api_leaves_unsafe_projected_event_eta_unavailable(...):
    ...
    assert poi["eta_seconds"] is None
    assert poi["estimated_arrival_time"] is None
```

Add a separate behind-aircraft case whose stored segment is before the nearest
current route point. Assert the event is not `upcoming` and has null timing.

- [ ] **Step 2: Run the unsafe-input tests to verify RED**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  -k 'unsafe_projected_event or projected_event_behind_aircraft' -q
```

Expected: at least the malformed tuple/behind-route tests fail until validation
is complete. Record which condition exposed the missing guard.

- [ ] **Step 3: Make validation fail closed without broad exception behavior**

Validate finite current coordinates, speed, projected coordinates, progress,
and calculated segment speed with `math.isfinite`; bound latitude to `[-90, 90]`,
longitude to `[-180, 180]`, progress to `[0, 100]`, and segment index to
`0 <= index < len(active_route.points) - 1`. Return `None` before distance
calculation for any failure. Return `None` when current route position is after
the stored destination segment.

Do not change the endpoint to synthesize a replacement ETA.

- [ ] **Step 4: Run unsafe-input tests to verify GREEN**

Run the exact command from Step 2.

Expected: PASS; endpoint timing fields are null for every unsafe case.

- [ ] **Step 5: Verify simulation and existing no-telemetry behavior**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  -k 'in_flight or unavailable_without_in_flight_telemetry' -q
```

Expected: deterministic in-memory simulated telemetry succeeds without a
physical aircraft; missing telemetry preserves the existing unavailable result.

- [ ] **Step 6: Commit the fail-closed slice**

```bash
git add backend/starlink-location/app/services/eta/projection.py \
  backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py
git commit -m "fix(overview): fail closed for unsafe mission event ETA"
```

### Task 4: Clarify ETA provenance in the Overview panel

**Files:**

- Modify: `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx`.
- Modify: `frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx`.
- Modify: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`.

**Interfaces:**

- Consumes: `estimated_arrival_time` and `eta_type` from
  `OverviewUpcomingPoi`.
- Produces: UTC-only ordinary estimates, explicit anticipated rows, and `ETA
  unavailable` for null/invalid timing.

- [ ] **Step 1: Write the failing panel test**

Add a test that renders one estimated and one anticipated POI:

```tsx
expect(screen.getByText('2026-09-22 12:02 UTC')).not.toBeNull();
expect(screen.getByText('2026-09-22 12:01 UTC · anticipated')).not.toBeNull();
expect(screen.queryByText(/UTC · estimated/)).toBeNull();
```

Keep the existing null/invalid timing assertion unchanged.

- [ ] **Step 2: Run the panel test to verify RED**

```bash
npm --prefix frontend/mission-planner test -- \
  src/pages/UpcomingPoisPanel.test.tsx
```

Expected: FAIL because the current label appends `estimated` to ordinary rows.

- [ ] **Step 3: Implement the minimal label policy**

Update `etaLabel()`:

```tsx
const utc = `${date.slice(0, 10)} ${date.slice(11, 16)} UTC`;
return etaType === 'estimated' ? utc : `${utc} · anticipated`;
```

Leave null/invalid handling and the `ETA` column header unchanged.

- [ ] **Step 4: Run the panel test to verify GREEN**

Run the exact command from Step 2.

Expected: PASS, including `ETA unavailable` behavior.

- [ ] **Step 5: Add the browser contract and run it at 1920x1080**

Update the existing upcoming-POI browser journey to assert the panel does not
contain `estimated`, still contains the anticipated qualifier, and retains the
existing exact viewport assertion. Run the repository's focused Playwright
command for `overview-globe.spec.ts` with its configured 1920x1080 project.

Expected: PASS with fresh native browser evidence; do not replace it with a
standalone browser, local Vite probe, or screenshot-only claim.

- [ ] **Step 6: Commit the presentation slice**

```bash
git add frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx \
  frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx \
  frontend/mission-planner/tests/e2e/overview-globe.spec.ts
git commit -m "fix(overview): clarify upcoming ETA provenance"
```

### Task 5: Document and verify the complete delivery

**Files:**

- Modify: `docs/api/endpoints/overview-upcoming-pois.md`.
- Modify: `docs/features/overview.md`.

**Interfaces:**

- Consumes: final endpoint semantics and panel wording from Tasks 2–4.
- Produces: truthful operator/developer documentation without a changed API
  schema.

- [ ] **Step 1: Write a failing documentation assertion**

Extend the existing docs test or add a narrow assertion that requires the
endpoint reference to state all three facts:

```python
assert "stored route-segment projection" in text
assert "no direct-coordinate ETA fallback" in text
assert "ETA unavailable" in text
```

The assertion must target `docs/api/endpoints/overview-upcoming-pois.md`, not a
broad documentation glob.

- [ ] **Step 2: Run the documentation test to verify RED**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest tools/tests/test_acceptance_platform_docs.py -q
```

Expected: FAIL only if the selected existing docs-test location owns this
contract. If it does not, add the focused assertion to the repository's actual
docs test module discovered before editing, then rerun that exact test path.

- [ ] **Step 3: Update the endpoint and feature documents**

Document that generated events use their stored interior route projection;
current speed is blended only on the current route portion; later segments use
planned speed; and unsafe projection, geometry, direction, or telemetry leaves
ETA unavailable. State that ordinary estimates show UTC and anticipated times
carry the explicit qualifier.

Do not claim the result is telemetry or schedule truth.

- [ ] **Step 4: Run the documentation test to verify GREEN**

Run the exact test command established in Step 2.

Expected: PASS.

- [ ] **Step 5: Run complete changed-scope verification**

```bash
uv run --with-requirements backend/starlink-location/requirements-dev.txt \
  pytest backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py -q
npm --prefix frontend/mission-planner test -- src/pages/UpcomingPoisPanel.test.tsx
ACCEPTANCE_POLICY_BASE_SHA=$(git merge-base HEAD origin/dev) ./tools/verify static
git diff --check origin/dev...HEAD
git status --short
```

Expected: every command passes, the diff has no whitespace errors, and no
untracked/generated artifact is staged.

- [ ] **Step 6: Commit documentation and final local verification**

```bash
git add docs/api/endpoints/overview-upcoming-pois.md docs/features/overview.md
# Add only the focused documentation test if one was actually changed.
git commit -m "docs(overview): explain route-aware mission event ETA"
git push origin HEAD
git ls-remote --heads origin refs/heads/fix/issue-177-route-aware-eta
```

Expected: the remote SHA equals local `HEAD`; report each RED/GREEN result,
exact changed files, browser evidence handle, static results, and any honestly
unverified aggregate test limitation.
