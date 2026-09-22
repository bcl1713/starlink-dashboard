<!-- markdownlint-disable-file MAX_LINES MD013 MD032 MD060 -->

# V2 Mission Single-Source and V1 Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a persisted active v2 mission leg the sole mission context for Overview and mission-bound POIs, then remove the v1 mission runtime/API without touching legacy volume files.

**Architecture:** Introduce a v2-owned resolver that returns either a complete `ActiveMissionLegContext` or a named failure state after validating persisted hierarchical missions against `RouteManager`. Route v2 activation, Overview, and generic POI status use that resolver; v1 routing and flat-storage behavior are deleted rather than translated. The frontend retains its existing projection/rendering pipeline and only consumes the expanded public state contract.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, filelock, pytest; TypeScript/React 19, TanStack Query, Vitest, Playwright/Chromium; Docker Compose; Markdown.

**Spec:** `docs/superpowers/specs/2026-09-22-v2-mission-single-source-design.md`

## Global Constraints

- Base implementation work on freshly fetched `origin/dev`, currently `b2086bc9c57ccd029d0982e78237d7471c504928`; create `/home/brian/starlink-dashboard-v2-mission-retirement` as the isolated feature worktree and target its PR to `dev`.
- `main` is a separate Brian-reviewed release gate; never target or merge this delivery to `main`.
- `/api/v2/missions/{mission_id}/legs/{leg_id}/activate` is the sole supported mission-activation command.
- `/api/missions` and every former v1 subroute must be absent and return normal `404 Not Found`; do not redirect, proxy, or translate them.
- Flat v1 artifacts in `data/missions/*.json`, `*.sha256`, and flat timeline files are retained, inert, byte-for-byte unchanged, and never read, rewritten, migrated, or deleted.
- A supported active mission is exactly one persisted v2 leg whose parent, leg, route ID, and active `ParsedRoute` validate together.
- Route-only activation remains supported but must not create mission-scoped Overview context or POIs.
- Preserve active-route behavior, route-aware ETA semantics, trusted `generated_source="mission-timeline"` provenance, Top-5 ordering, marker retention, and Grafana behavior.
- Do not change route CRUD/import, flight-state calculation, telemetry simulation, manual/global POI behavior, or add automatic v1-to-v2 migration.
- Backend changes must remain typed and formatted with Black/Ruff; frontend remains TypeScript strict and uses the existing lint/build tooling.
- Keep files cohesive; do not grow unrelated files past the repository’s 300-line guard without an explicit justification.
- Documentation impact is in scope: Overview API/feature documentation, mission operator workflows, troubleshooting/export guidance, and release-policy breaking-change notes. No Grafana documentation change is needed.
- Final browser acceptance is required at the immutable implementation SHA through a fresh CDP-attached Chromium session at exact 1920×1080 CSS viewport/DPR 1. Playwright coverage is additional, not a substitute.

## Review Focus

- Two concurrently persisted active legs in different parent directories must yield `inconsistent_active_mission` and no POIs; no arbitrary parent/leg may be selected.
- A route-only active route with no v2 active leg must yield `no_active_mission`, not the misleading claim that no route is active.
- An active v2 leg whose route is empty, missing, or differs from `RouteManager`’s active route must yield `route_unavailable`, no POIs, and no raw IDs in UI copy.
- A route activation or timeline-generation failure after persisted flags change must restore prior flags and leave no unresolvable successful active context.
- Flat v1 JSON/checksum/timeline artifacts alongside v2 mission directories must survive startup, resolver reads, v2 activation, and Overview projection unchanged.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/starlink-location/app/mission/active_context.py` | V2-owned typed active-leg resolution, explicit outcomes, and bounded diagnostics. |
| `backend/starlink-location/app/mission/storage.py` | V2 hierarchy persistence plus a repository-wide active-leg lock; no flat-v1 storage or timeline fallback. |
| `backend/starlink-location/app/services/route_manager.py` | Public active-route identity accessor used by the resolver and POI rules. |
| `backend/starlink-location/app/mission/routes_v2.py` | Transactional global v2 activation/deactivation using scoped v2 persistence. |
| `backend/starlink-location/app/api/overview_upcoming_pois.py` | Resolver-backed endpoint while retaining ETA/projection services. |
| `backend/starlink-location/app/models/overview_upcoming_pois.py` | Public explicit Overview state union. |
| `backend/starlink-location/app/api/pois/helpers.py` | Resolver-backed mission-bound POI active-status rule. |
| `backend/starlink-location/main.py` | V2-only router registration. |
| `backend/starlink-location/app/mission/routes/` | Delete: retired v1 router/runtime only. |
| `backend/starlink-location/tests/unit/test_active_mission_context.py` | New resolver/failure/inert-storage test seam. |
| `backend/starlink-location/tests/integration/test_mission_routes_v2.py` | Global exclusivity, compensation, restart, and route lifecycle integration tests. |
| `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py` | Persisted v2-context Overview, ETA/provenance, and unavailable-state API tests. |
| `backend/starlink-location/tests/unit/test_poi_manager.py` | Generic/global/route-only/mission-bound active-status matrix. |
| `backend/starlink-location/tests/unit/test_router_integration.py` | Former-v1-404 and v2-availability route assertions. |
| `frontend/mission-planner/src/services/overview-upcoming-pois.ts` | Matching TypeScript state union; endpoint unchanged. |
| `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx` | Truthful compact no-data copy without identifiers. |
| `frontend/mission-planner/tests/e2e/v2-mission-overview.spec.ts` | Stateful browser activation-to-Overview contract with no v1 request. |
| `docs/api/endpoints/overview-upcoming-pois.md` and `docs/features/overview.md` | Public v2 context/state contract and preserved lifecycle behavior. |
| `docs/missions/README.md`, `docs/missions/sop/pre-flight.md`, `docs/comm-sop/in-flight-operations.md`, `docs/features/mission-planning.md`, `docs/troubleshooting/data-issues.md`, `docs/reports/analysis-reports/exporter/README.md` | Replace legacy activation/export guidance with supported v2 flows or clearly retire obsolete instructions. |
| `docs/development/release-policy.md` | Record the required major-version/breaking API note for `/api/missions` removal and retained inert files. |

### Task 1: Define and test the active v2 mission-context resolver

**Files:**
- Create: `backend/starlink-location/app/mission/active_context.py`
- Modify: `backend/starlink-location/app/mission/storage.py`
- Modify: `backend/starlink-location/app/services/route_manager.py`
- Create: `backend/starlink-location/tests/unit/test_active_mission_context.py`
- Test: `backend/starlink-location/tests/unit/test_route_manager.py`

**Interfaces:**
- Consumes: `list_mission_metadata_v2() -> list[Mission]`, `load_mission_v2(mission_id: str) -> Mission | None`, `RouteManager.get_route(route_id: str) -> ParsedRoute | None`, and `RouteManager.get_active_route() -> ParsedRoute | None`.
- Produces: `ActiveMissionLegContext(parent_mission_id: str, parent_mission: Mission, leg: MissionLeg, route_id: str, route: ParsedRoute)` and `resolve_active_mission_leg_context(route_manager: RouteManager) -> ActiveMissionLegResolution` where `state` is exactly `"available" | "no_active_mission" | "route_unavailable" | "inconsistent_active_mission"` and `context` is present only for `available`.
- Produces: `RouteManager.get_active_route_id() -> str | None`, returning the manager’s active ID rather than deriving it from route metadata.

- [ ] **Step 0: Create and verify the execution worktree**

Use `superpowers:using-git-worktrees`, then create the named worktree from the freshly fetched integration ref and establish a feature upstream:

```bash
cd /home/brian/starlink-dashboard
git fetch origin
git worktree add -b feat/v2-mission-retirement \
  /home/brian/starlink-dashboard-v2-mission-retirement origin/dev
git -C /home/brian/starlink-dashboard-v2-mission-retirement push -u origin HEAD
git -C /home/brian/starlink-dashboard-v2-mission-retirement branch -vv
git -C /home/brian/starlink-dashboard-v2-mission-retirement rev-parse HEAD
```

Expected: the feature worktree starts at the fetched `origin/dev` SHA, tracks `origin/feat/v2-mission-retirement`, and no shared integration checkout is modified.

- [ ] **Step 1: Write resolver tests before production code**

Create `tests/unit/test_active_mission_context.py` with fixtures that write two v2 parent directories through `save_mission_v2` and a `RouteManager` loaded with parsed routes. Test a fresh resolver instance after reloading storage, zero legs, exactly one valid leg, empty/missing route, active-route mismatch, and two active legs across parents:

```python
def test_resolver_returns_parent_leg_and_route_after_fresh_read(route_manager, v2_mission):
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    assert route_manager.activate_route("route-a") is True

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == "available"
    assert resolution.context.parent_mission_id == v2_mission.id
    assert resolution.context.leg.id == "leg-a"
    assert resolution.context.route_id == "route-a"


@pytest.mark.parametrize("state_setup, expected", [
    ("none", "no_active_mission"),
    ("missing_route", "route_unavailable"),
    ("route_mismatch", "route_unavailable"),
    ("two_active_legs", "inconsistent_active_mission"),
])
def test_resolver_returns_explicit_failure_without_context(state_setup, expected, route_manager):
    arrange_v2_state(state_setup, route_manager)

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == expected
    assert resolution.context is None
```

Add a route-manager assertion that `get_active_route_id()` is `None` before activation and returns the requested route ID afterward.

- [ ] **Step 2: Run the new unit test to verify it fails**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/unit/test_active_mission_context.py tests/unit/test_route_manager.py -v
```

Expected: FAIL because `app.mission.active_context` and `RouteManager.get_active_route_id()` do not exist.

- [ ] **Step 3: Implement the narrow resolver and V2-only storage lock**

Add a frozen context/outcome model and make resolution read persisted v2 parents on every call. Do not search flat files or infer context from POI labels/current route. Add a repository-wide lock distinct from the existing parent lock:

```python
@dataclass(frozen=True)
class ActiveMissionLegContext:
    parent_mission_id: str
    parent_mission: Mission
    leg: MissionLeg
    route_id: str
    route: ParsedRoute


@dataclass(frozen=True)
class ActiveMissionLegResolution:
    state: ActiveMissionLegState
    context: ActiveMissionLegContext | None = None


def get_active_leg_lock() -> FileLock:
    ensure_missions_directory()
    return FileLock(str(MISSIONS_DIR / ".active-leg.lock"))
```

Resolver rules: collect all `leg.is_active`; return `no_active_mission` for zero, `inconsistent_active_mission` for more than one; require a nonblank route ID, existing route, `get_active_route_id() == route_id`, and matching active route before returning context. Log only parent ID, leg ID, expected route ID, observed route ID, and failure state.

- [ ] **Step 4: Run focused tests and formatters**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/unit/test_active_mission_context.py tests/unit/test_route_manager.py -v
uv run --with-requirements requirements.txt black --check --diff app/mission/active_context.py app/mission/storage.py app/services/route_manager.py tests/unit/test_active_mission_context.py tests/unit/test_route_manager.py
uv run --with-requirements requirements.txt ruff check app/mission/active_context.py app/mission/storage.py app/services/route_manager.py tests/unit/test_active_mission_context.py tests/unit/test_route_manager.py
```

Expected: PASS; resolution never reads non-directory/flat v1 storage.

- [ ] **Step 5: Commit the resolver contract**

```bash
git add backend/starlink-location/app/mission/active_context.py \
  backend/starlink-location/app/mission/storage.py \
  backend/starlink-location/app/services/route_manager.py \
  backend/starlink-location/tests/unit/test_active_mission_context.py \
  backend/starlink-location/tests/unit/test_route_manager.py
git commit -m "feat(missions): resolve active v2 mission context"
```

### Task 2: Make v2 activation globally exclusive and compensated on failure

**Files:**
- Modify: `backend/starlink-location/app/mission/routes_v2.py`
- Modify: `backend/starlink-location/app/mission/storage.py`
- Modify: `backend/starlink-location/tests/integration/test_mission_routes_v2.py`
- Modify: `backend/starlink-location/tests/integration/test_adjusted_departure_integration.py`
- Test: `backend/starlink-location/tests/integration/test_mission_v2_bug_repro.py`

**Interfaces:**
- Consumes: `get_active_leg_lock() -> FileLock`, all v2 `Mission` persistence functions, `RouteManager.activate_route(route_id: str) -> bool`, `RouteManager.deactivate_route(route_id: str | None = None) -> None`, and scoped `save_mission_timeline(..., parent_mission_id: str)`.
- Produces: v2 activation where exactly one persisted v2 leg is active after `200`, or every persisted active flag is restored and the response is non-2xx; deactivation that affects route/clock state only when its parent owns the global active leg.

- [ ] **Step 1: Write cross-parent and compensation integration tests**

In `test_mission_routes_v2.py`, create two stored parent missions with different routes. Activate parent A then parent B; reload both parents from disk and assert only B’s requested leg is active. Add injected failure tests for route activation and timeline build/save:

```python
async def test_activation_clears_active_leg_in_other_parent(client, two_parent_missions):
    await activate(client, "mission-a", "leg-a")
    response = await activate(client, "mission-b", "leg-b")

    assert response.status_code == 200
    assert load_mission_v2("mission-a").legs[0].is_active is False
    assert load_mission_v2("mission-b").legs[0].is_active is True


async def test_timeline_failure_restores_flags_and_returns_non_2xx(client, monkeypatch, two_parent_missions):
    await activate(client, "mission-a", "leg-a")
    monkeypatch.setattr("app.mission.routes_v2.build_mission_timeline", raise_timeline_error)

    response = await activate(client, "mission-b", "leg-b")

    assert response.status_code >= 400
    assert load_mission_v2("mission-a").legs[0].is_active is True
    assert load_mission_v2("mission-b").legs[0].is_active is False
```

Also test a deactivation request for an inactive parent does not deactivate the globally active parent’s route/clock. Keep the existing parent-ID timeline assertion and explicitly retain `generated_source == "mission-timeline"`.

- [ ] **Step 2: Run tests to verify current behavior fails**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/integration/test_mission_routes_v2.py tests/integration/test_adjusted_departure_integration.py -v
```

Expected: FAIL because current activation only locks/deactivates siblings, ignores route/timeline failure, and deactivation is parent-local.

- [ ] **Step 3: Implement the ordered global activation transaction with compensation**

Inside `get_active_leg_lock()`: load/validate target first; snapshot every affected parent’s active flags; set the selected leg and clear all others; persist changed parents; activate target route; build and save its parent-scoped timeline; only then apply existing flight/operational-clock state. If any post-persist operation fails, restore every changed parent from the snapshot, deactivate the target route if it was newly selected, restore the previously active route where one existed, and return/raise a non-2xx `HTTPException`.

Use the existing `get_mission_lock(parent_id)` while saving each affected parent in deterministic sorted parent-ID order; the repository lock remains the outer lock. Do not claim success if `activate_route` returns `False` unless the active route ID already equals the target ID. Preserve real failure detail in server logs only.

- [ ] **Step 4: Run focused integration tests and formatting checks**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/integration/test_mission_routes_v2.py tests/integration/test_adjusted_departure_integration.py tests/integration/test_mission_v2_bug_repro.py -v
uv run --with-requirements requirements.txt black --check --diff app/mission/routes_v2.py app/mission/storage.py tests/integration/test_mission_routes_v2.py tests/integration/test_adjusted_departure_integration.py
uv run --with-requirements requirements.txt ruff check app/mission/routes_v2.py app/mission/storage.py tests/integration/test_mission_routes_v2.py tests/integration/test_adjusted_departure_integration.py
```

Expected: PASS; every successful activation resolves through Task 1’s resolver after a fresh storage read.

- [ ] **Step 5: Commit the lifecycle invariant**

```bash
git add backend/starlink-location/app/mission/routes_v2.py \
  backend/starlink-location/app/mission/storage.py \
  backend/starlink-location/tests/integration/test_mission_routes_v2.py \
  backend/starlink-location/tests/integration/test_adjusted_departure_integration.py
git commit -m "fix(missions): make v2 activation globally exclusive"
```

### Task 3: Move Overview and generic POI status to v2 context

**Files:**
- Modify: `backend/starlink-location/app/api/overview_upcoming_pois.py`
- Modify: `backend/starlink-location/app/models/overview_upcoming_pois.py`
- Modify: `backend/starlink-location/app/api/pois/helpers.py`
- Modify: `backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py`
- Modify: `backend/starlink-location/tests/unit/test_overview_upcoming_pois.py`
- Modify: `backend/starlink-location/tests/unit/test_poi_manager.py`

**Interfaces:**
- Consumes: `resolve_active_mission_leg_context(route_manager)` from Task 1 and `ActiveMissionLegResolution.state`.
- Produces: `OverviewUpcomingPoisState = Literal["available", "no_active_mission", "route_unavailable", "inconsistent_active_mission", "no_generated_pois", "no_upcoming_pois", "unavailable"]`; no `no_active_route` state remains.
- Produces: `calculate_poi_active_status(poi: POI, route_manager: RouteManager | None) -> bool` that checks mission context before the route-only branch for a POI with `mission_id`.

- [ ] **Step 1: Replace legacy Overview monkeypatches with persisted v2 fixtures**

Rewrite `test_overview_upcoming_pois_api.py` fixtures to create a v2 parent + active leg + matching active route and timeline-generated POIs. Remove every `get_active_mission_id` monkeypatch. Add explicit tests:

```python
@pytest.mark.parametrize("setup, expected_state", [
    ("route_only_active", "no_active_mission"),
    ("missing_leg_route", "route_unavailable"),
    ("mismatched_active_route", "route_unavailable"),
    ("two_persisted_active_legs", "inconsistent_active_mission"),
])
def test_overview_context_failures_return_no_pois(client, setup, expected_state):
    arrange_v2_overview_context(setup)

    response = client.get("/api/overview/upcoming-pois")

    assert response.status_code == 200
    assert response.json()["state"] == expected_state
    assert response.json()["pois"] == []


def test_overview_reads_only_trusted_generated_pois_for_v2_parent(client):
    arrange_active_v2_context_with_manual_and_generated_pois()

    payload = client.get("/api/overview/upcoming-pois").json()

    assert payload["state"] == "available"
    assert {poi["kind"] for poi in payload["pois"]} >= {"departure", "arrival"}
    assert "manual-poi-id" not in {poi["poi_id"] for poi in payload["pois"]}
```

Retain existing late-departure, speed-change, route-detour, missing-telemetry, lifecycle filter, ordering, and 60-minute retention assertions through the persisted V2 arrangement.

- [ ] **Step 2: Write mission-bound POI status matrix tests**

Add unit cases proving global POIs remain active, route-only POIs follow active route, mission-bound POIs require matching v2 parent, mission-plus-route POIs require both parent and leg route, and missing/inconsistent/mismatched v2 context makes mission-bound POIs inactive:

```python
def test_mission_and_route_bound_poi_requires_matching_v2_parent_and_leg_route(route_manager):
    arrange_active_v2_context("mission-a", "leg-a", "route-a", route_manager)
    poi = POI(id="generated", mission_id="mission-a", route_id="route-b", ...)

    assert calculate_poi_active_status(poi, route_manager) is False
```

- [ ] **Step 3: Run tests to verify the old v1 dependency fails**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/integration/test_overview_upcoming_pois_api.py tests/unit/test_overview_upcoming_pois.py tests/unit/test_poi_manager.py -v
```

Expected: FAIL until the endpoint and helper consume Task 1’s resolver and the response union accepts the new states.

- [ ] **Step 4: Implement resolver-backed consumers without changing ETA projection**

Map resolver failure states one-for-one to `OverviewUpcomingPoisResponse(state=..., pois=[])`. For `available`, use `context.parent_mission_id` to load POIs and `context.route` for `calculate_route_aware_eta_results`; preserve `project_overview_upcoming_pois` unchanged. Never fall back to v1 records/current route.

In POI helper, handle `mission_id is not None` first:

```python
resolution = resolve_active_mission_leg_context(route_manager)
if resolution.context is None:
    return False
if poi.mission_id != resolution.context.parent_mission_id:
    return False
return poi.route_id is None or poi.route_id == resolution.context.route_id
```

Then preserve the existing route-only and global branches, replacing route metadata extraction with `get_active_route_id()`.

- [ ] **Step 5: Run focused tests and static checks**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/integration/test_overview_upcoming_pois_api.py tests/unit/test_overview_upcoming_pois.py tests/unit/test_poi_manager.py -v
uv run --with-requirements requirements.txt black --check --diff app/api/overview_upcoming_pois.py app/models/overview_upcoming_pois.py app/api/pois/helpers.py tests/integration/test_overview_upcoming_pois_api.py tests/unit/test_overview_upcoming_pois.py tests/unit/test_poi_manager.py
uv run --with-requirements requirements.txt ruff check app/api/overview_upcoming_pois.py app/models/overview_upcoming_pois.py app/api/pois/helpers.py tests/integration/test_overview_upcoming_pois_api.py tests/unit/test_overview_upcoming_pois.py tests/unit/test_poi_manager.py
```

Expected: PASS; existing established ETA/lifecycle tests pass under v2 context.

- [ ] **Step 6: Commit the consumer migration**

```bash
git add backend/starlink-location/app/api/overview_upcoming_pois.py \
  backend/starlink-location/app/models/overview_upcoming_pois.py \
  backend/starlink-location/app/api/pois/helpers.py \
  backend/starlink-location/tests/integration/test_overview_upcoming_pois_api.py \
  backend/starlink-location/tests/unit/test_overview_upcoming_pois.py \
  backend/starlink-location/tests/unit/test_poi_manager.py
git commit -m "fix(overview): derive mission pois from v2 context"
```

### Task 4: Retire v1 routes and flat runtime persistence safely

**Files:**
- Modify: `backend/starlink-location/main.py`
- Modify: `backend/starlink-location/app/mission/__init__.py`
- Modify: `backend/starlink-location/app/mission/storage.py`
- Delete: `backend/starlink-location/app/mission/routes/__init__.py`
- Delete: `backend/starlink-location/app/mission/routes/activation.py`
- Delete: `backend/starlink-location/app/mission/routes/missions.py`
- Delete: `backend/starlink-location/app/mission/routes/operations.py`
- Delete: `backend/starlink-location/app/mission/routes/utils.py`
- Delete: `backend/starlink-location/tests/integration/test_mission_routes.py`
- Delete: `backend/starlink-location/tests/unit/test_mission_routes_validation.py`
- Modify: `backend/starlink-location/tests/conftest.py`
- Modify: `backend/starlink-location/tests/unit/test_mission_storage.py`
- Modify: `backend/starlink-location/tests/unit/test_router_integration.py`
- Modify: `backend/starlink-location/tests/integration/test_mission_scenarios.py`

**Interfaces:**
- Consumes: scoped v2 storage only: parent directory/file, leg file, `save_mission_v2`, `load_mission_v2`, `list_mission_metadata_v2`, `get_mission_lock`, `get_active_leg_lock`, and parent-required timeline save/load/delete functions.
- Produces: no importable `app.mission.routes`, no registered `/api/missions` router, and all v1 endpoints return FastAPI 404 while `/api/v2/missions` remains registered.

- [ ] **Step 1: Add 404 and flat-artifact regression tests**

Replace v1 router expectations with parameterized absence checks:

```python
@pytest.mark.parametrize("path", [
    "/api/missions",
    "/api/missions/active",
    "/api/missions/active/timeline",
    "/api/missions/example/activate",
    "/api/missions/example/export/pdf",
])
def test_legacy_mission_routes_are_not_registered(client, path):
    assert client.get(path).status_code == 404


def test_v2_route_remains_registered(client):
    assert client.get("/api/v2/missions").status_code != 404
```

In storage tests, create bytes for `legacy.json`, `legacy.sha256`, and `legacy-leg.timeline.json` beside a valid v2 directory, run app startup/resolver/activation/Overview arrangement, then compare `read_bytes()` to the original fixtures. Also assert v2 listing ignores non-directories and scoped timeline reads never inspect or migrate flat files.

- [ ] **Step 2: Run retirement tests to verify current code fails**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/unit/test_router_integration.py tests/unit/test_mission_storage.py tests/integration/test_mission_scenarios.py -v
```

Expected: FAIL because v1 routes are registered, flat storage helpers/fallbacks exist, and `conftest.py` imports v1 global state.

- [ ] **Step 3: Delete only v1 runtime and remove flat storage behavior**

Remove the legacy import/router registration from `main.py`, delete `app/mission/routes/`, and remove test fixture resets of `_active_mission_id`. In `storage.py`, remove flat mission/checksum CRUD and unscoped timeline fallback/migration/deletion. Make the scoped timeline API require `parent_mission_id: str` so omission cannot silently reopen v1 files:

```python
def get_leg_timeline_path(leg_id: str, parent_mission_id: str) -> Path:
    return get_mission_legs_dir(parent_mission_id) / f"{leg_id}{TIMELINE_SUFFIX}"
```

Search every production import after deletion and update only consumers that need retained v2 primitives. Preserve `MissionLeg` as v2 child model, v2 directories, v2 leg timelines, and locks. Do not delete data files and do not add a migration.

- [ ] **Step 4: Run targeted tests, import audit, and formatters**

Run:

```bash
cd /home/brian/starlink-dashboard-v2-mission-retirement
git grep -n -E 'app\.mission\.routes|load_mission\(|save_mission\(|list_missions\(|get_active_mission_id|/api/missions' -- backend/starlink-location/app backend/starlink-location/tests
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/unit/test_router_integration.py tests/unit/test_mission_storage.py tests/integration/test_mission_scenarios.py tests/integration/test_mission_routes_v2.py -v
uv run --with-requirements requirements.txt black --check --diff app tests
uv run --with-requirements requirements.txt ruff check app tests
```

Expected: grep has no production v1 runtime references; any remaining `/api/missions` test reference is an explicit 404 assertion or documentation test; test suite passes.

- [ ] **Step 5: Commit the breaking retirement**

```bash
git add backend/starlink-location
git commit -m "feat(missions): retire legacy v1 mission api"
```

### Task 5: Update frontend states without changing Overview lifecycle behavior

**Files:**
- Modify: `frontend/mission-planner/src/services/overview-upcoming-pois.ts`
- Modify: `frontend/mission-planner/src/services/overview-upcoming-pois.test.ts`
- Modify: `frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx`
- Modify: `frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx`
- Test: `frontend/mission-planner/src/pages/overview-upcoming-pois.test.ts`
- Test: `frontend/mission-planner/src/pages/OverviewPoiMarker.test.ts`

**Interfaces:**
- Consumes: backend state union from Task 3 at unchanged `GET /api/overview/upcoming-pois`.
- Produces: `OverviewUpcomingPoisResponse['state']` matching Task 3 exactly; `UpcomingPoisPanel` copy that tells operators the difference between no active v2 leg, missing/mismatched leg route, and persisted conflicting active legs.

- [ ] **Step 1: Write failing response and panel-copy tests**

Replace the `no_active_route` fixture in `UpcomingPoisPanel.test.tsx` with exact expected compact copy and no identifier leakage:

```tsx
it.each([
  ['no_active_mission', 'No active mission leg.'],
  ['route_unavailable', 'Active mission leg is not bound to the active route.'],
  ['inconsistent_active_mission', 'Active mission state is inconsistent.'],
] as const)('renders truthful %s copy', (state, message) => {
  render(<UpcomingPoisPanel state={state} pois={[]} currentTime={now} />);

  expect(screen.getByText(message)).toBeVisible();
  expect(screen.queryByText(/mission-[a-z0-9]/i)).not.toBeInTheDocument();
});
```

Add a compile-time/fixture test in the service tests with all seven valid states. Preserve existing unavailable alert role, Top-5 cap, order, no-scroll table body, retained marker projection, and label tests unchanged.

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run:

```bash
cd frontend/mission-planner
NODE_ENV=test npx vitest run src/services/overview-upcoming-pois.test.ts src/pages/UpcomingPoisPanel.test.tsx src/pages/overview-upcoming-pois.test.ts src/pages/OverviewPoiMarker.test.ts
```

Expected: FAIL because `no_active_route` is still the client union and state message map.

- [ ] **Step 3: Implement the matching state union and messages**

Remove `no_active_route`, add `no_active_mission`, `route_unavailable`, and `inconsistent_active_mission` in the typed response and `STATE_MESSAGES`. Do not alter polling cadence/retry behavior in `useOverviewUpcomingPois`, `overviewPoiView`, `OverviewPage` marker retention, urgency, Top-5, CSS layout, or canvas rendering.

- [ ] **Step 4: Run focused tests, lint, and production build**

Run:

```bash
cd frontend/mission-planner
NODE_ENV=test npx vitest run src/services/overview-upcoming-pois.test.ts src/pages/UpcomingPoisPanel.test.tsx src/pages/overview-upcoming-pois.test.ts src/pages/OverviewPoiMarker.test.ts
npm run lint
npm run build
```

Expected: PASS; TypeScript proves the API-state contract is exhaustive.

- [ ] **Step 5: Commit frontend state contract**

```bash
git add frontend/mission-planner/src/services/overview-upcoming-pois.ts \
  frontend/mission-planner/src/services/overview-upcoming-pois.test.ts \
  frontend/mission-planner/src/pages/UpcomingPoisPanel.tsx \
  frontend/mission-planner/src/pages/UpcomingPoisPanel.test.tsx
git commit -m "fix(overview): distinguish v2 mission context states"
```

### Task 6: Add browser and deployment-path evidence for v2 activation to Overview

**Files:**
- Create: `frontend/mission-planner/tests/e2e/v2-mission-overview.spec.ts`
- Modify: `frontend/mission-planner/tests/e2e/support/configured-origin.ts` only if a reusable stateful fixture helper is needed
- Test: `frontend/mission-planner/tests/e2e/overview-globe.spec.ts`

**Interfaces:**
- Consumes: Mission UI `useActivateLeg` request `POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate`, unchanged Overview endpoint, and Task 5 state messages.
- Produces: a stateful E2E fixture that records the v2 activation request, makes generated POIs available only afterward, and proves no `/api/missions` request occurred.

- [ ] **Step 1: Write the stateful browser test first**

Create a focused spec rather than expanding the existing large globe suite. Route fixtures must expose one inactive v2 parent/leg and only return `available` POIs after the actual activation POST:

```ts
let activated = false;
let legacyRequest = false;

await page.route('**/api/v2/missions/v2-parent/legs/v2-leg/activate', async route => {
  expect(route.request().method()).toBe('POST');
  activated = true;
  await route.fulfill({ status: 200, json: { leg_id: 'v2-leg' } });
});
await page.route('**/api/overview/upcoming-pois', async route => {
  await route.fulfill({ json: activated ? generatedOverviewPois : noActiveMission });
});
await page.on('request', request => {
  if (new URL(request.url()).pathname.startsWith('/api/missions')) legacyRequest = true;
});
```

Activate through the Mission page button, navigate to Overview, assert v2 generated departure/arrival data, retained star markers, exactly five non-scrollable rows, and `legacyRequest === false`. Add browser copy assertions for `no_active_mission` and `route_unavailable`.

- [ ] **Step 2: Run the new spec to verify failure**

Run:

```bash
cd frontend/mission-planner
npx playwright test tests/e2e/v2-mission-overview.spec.ts --project=chromium --reporter=line
```

Expected: FAIL until stateful v2 fixtures and frontend states exist.

- [ ] **Step 3: Complete fixture wiring and rerun focused browser coverage**

Keep fixtures same-origin through configured-origin helpers. Do not make the test pass by directly fulfilling `available` before activation or by substituting a legacy endpoint. Preserve existing `overview-globe.spec.ts` visual snapshot/viewport coverage.

- [ ] **Step 4: Run all relevant browser tests**

Run:

```bash
cd frontend/mission-planner
npx playwright test tests/e2e/v2-mission-overview.spec.ts tests/e2e/overview-globe.spec.ts tests/e2e/overview-poi-responsive.spec.ts tests/e2e/mission-workflow.spec.ts --project=chromium --reporter=line
```

Expected: PASS at the tested implementation SHA.

- [ ] **Step 5: Commit browser contract coverage**

```bash
git add frontend/mission-planner/tests/e2e/v2-mission-overview.spec.ts frontend/mission-planner/tests/e2e/support/configured-origin.ts
git commit -m "test(overview): cover v2 mission activation flow"
```

### Task 7: Update operator/API documentation and release policy

**Files:**
- Create: `backend/starlink-location/tests/unit/test_mission_retirement_docs.py`
- Modify: `docs/api/endpoints/README.md`
- Modify: `docs/api/endpoints/overview-upcoming-pois.md`
- Modify: `docs/features/overview.md`
- Modify: `docs/missions/README.md`
- Modify: `docs/missions/sop/pre-flight.md`
- Modify: `docs/comm-sop/in-flight-operations.md`
- Modify: `docs/features/mission-planning.md`
- Modify: `docs/troubleshooting/data-issues.md`
- Modify: `docs/reports/analysis-reports/exporter/README.md`
- Modify: `docs/development/release-policy.md`

**Interfaces:**
- Consumes: final endpoint states from Task 3 and v2 endpoint paths from Tasks 2/4.
- Produces: no supported operational/documentation instruction using `/api/missions`; documented breaking API removal and explicit retained-inert legacy data policy.

- [ ] **Step 1: Write documentation contract checks**

Create `tests/unit/test_mission_retirement_docs.py` to assert maintained operator/API docs contain no usable `/api/missions` path and that Overview API docs enumerate all final states. The allowed exception is a clearly marked breaking-change statement such as `` `/api/missions` has been removed and now returns 404. ``

```python
def test_maintained_mission_docs_do_not_publish_legacy_api_examples():
    for path in MAINTAINED_MISSION_DOCS:
        text = Path(path).read_text()
        assert "curl -X POST http://localhost:8000/api/missions" not in text
        assert "/api/missions/active" not in text
```

- [ ] **Step 2: Run the doc check to verify current documentation fails**

Run the new focused doc test, then:

```bash
cd /home/brian/starlink-dashboard-v2-mission-retirement
markdownlint-cli2 "docs/**/*.md"
```

Expected: the new check fails because current operators are instructed to activate/timeline/export through v1 routes.

- [ ] **Step 3: Rewrite maintained guidance around v2 and the retirement boundary**

Document all final Overview states; make clear `no_active_mission` can coexist with a route-only active route. Replace legacy activation with `POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate`; where a v2 equivalent does not exist, remove the obsolete procedure rather than inventing one. State flat v1 files are retained but inert with no automatic migration/cleanup. In `release-policy.md`, record that this is a required **major** compatibility change due to `/api/missions` removal. Keep ETA provenance, Top-5, and map retention documentation intact.

- [ ] **Step 4: Run documentation validation and link/scope audit**

Run:

```bash
cd /home/brian/starlink-dashboard-v2-mission-retirement
markdownlint-cli2 "docs/**/*.md"
git grep -n -E '/api/missions(/|`|$)' -- docs README.md
python3 tools/check_filename_convention.py
```

Expected: lint and filename checks pass; grep returns only explicit removal/breaking-change text, never a runnable v1 operator command.

- [ ] **Step 5: Commit documentation and release note**

```bash
git add backend/starlink-location/tests/unit/test_mission_retirement_docs.py docs
git commit -m "docs(missions): document v2 activation retirement"
```

### Task 8: Independent review, full verification, and exact-SHA acceptance

**Files:**
- Create during verification: `/home/brian/.hermes/profiles/oracle/cache/acceptance/v2-mission-retirement/<implementation-sha>/`, a bounded evidence directory keyed by immutable commit SHA.
- Do not add runtime data, credentials, Docker volumes, screenshots, or generated reports to the product repository unless a reviewer explicitly requests a durable test fixture.

**Interfaces:**
- Consumes: all previous task contracts and immutable feature commit SHA.
- Produces: fresh verification evidence that the feature branch is reviewable, green, and behaviorally proven before a PR is requested/merged into `dev`.

- [ ] **Step 1: Run a fresh backend full suite and static checks**

Run:

```bash
cd backend/starlink-location
uv run --with-requirements requirements.txt pytest tests/ -v
uv run --with-requirements requirements.txt black --check --diff app tests
uv run --with-requirements requirements.txt ruff check app tests
```

Expected: all tests pass, including v2 resolver, cross-parent activation/rollback, V1 404, flat-artifact inertness, Overview ETA/provenance, and POI active-status matrix.

- [ ] **Step 2: Run a fresh frontend suite, lint, and build**

Run:

```bash
cd frontend/mission-planner
npm ci --legacy-peer-deps
npm run lint
npm run test:unit
npm run build
npx playwright test --project=chromium --reporter=line
```

Expected: all unit/E2E tests pass; screenshot changes, if any, are deliberately reviewed.

- [ ] **Step 3: Build and start a task-owned deployment path from the exact SHA**

From a clean detached worktree at the final feature SHA, record `git rev-parse HEAD`, then build/rebuild only the task-owned stack. Confirm backend/UI health and record image/container identifiers. Never use a shared live stack, delete volumes, or reuse an existing browser session.

- [ ] **Step 4: Perform exact CDP 1920×1080 acceptance on that SHA**

Launch fresh Chromium with a task-owned profile and CDP port; attach through CDP. Record `window.innerWidth`, `window.innerHeight`, `visualViewport.width`, `visualViewport.height`, `devicePixelRatio`, and screenshot raster. Require exactly `1920`, `1080`, `1920`, `1080`, and `1` respectively.

Through the Mission UI, activate a v2 leg. From the same deployment, read and retain redacted evidence for `/api/v2/missions` (selected leg active), `/api/flight-status`, `/api/overview/upcoming-pois` (v2-generated POIs/states), and `/api/missions` (404). Then navigate that same CDP page to Overview and prove retained departure/arrival stars, correct v2-generated POIs, exact five-row non-scrollable panel, and truthful unavailable copy. If viewport metrics or stack/SHA provenance differ, report an acceptance gap rather than substituting Playwright or an emulated viewport.

- [ ] **Step 5: Push, request independent task/branch reviews, and verify remote scope**

Before each review request, push all commits and verify the remote feature SHA and changed-file list:

```bash
git status --short
git branch -vv
git push
git ls-remote origin "refs/heads/feat/v2-mission-retirement"
git diff --name-status origin/dev...HEAD
```

Use `superpowers:subagent-driven-development` for implementation review after each task and a separate final whole-branch reviewer. Address only independently verified findings, rerun affected tests, and repeat this full verification after final changes. Open one PR targeting `dev`; do not merge until CI is green, remote review evidence is complete, and the exact-SHA browser gate passes.

## Plan Self-Review

- **Spec coverage:** Tasks 1–4 implement the single persisted v2 context, global activation, consumer migration, v1 removal, 404 boundary, inert data safety, diagnostics, and rollback. Task 5 covers truthful frontend states without lifecycle regressions. Task 6 covers browser activation flow. Task 7 covers API/operator/release documentation. Task 8 covers all stated test, review, deployment, and exact-CDP acceptance gates.
- **Placeholder scan:** No task contains an unfinished-marker, deferred implementation, or cross-task shorthand. Paths, commands, failure expectations, interfaces, and representative contract code are present.
- **Type consistency:** `ActiveMissionLegContext`, `ActiveMissionLegResolution`, `resolve_active_mission_leg_context`, `get_active_leg_lock`, and `get_active_route_id` are defined in Task 1 and consumed consistently by Tasks 2–4. The seven-state API union is defined in Task 3 and consumed unchanged in Task 5.
- **Review focus closure:** duplicate active legs (Task 1/3), route-only active state (Task 3/5/6), mismatched route (Task 1/3/5/6), activation compensation (Task 2), and inert flat artifacts (Task 4) each have named automated coverage and final verification.
