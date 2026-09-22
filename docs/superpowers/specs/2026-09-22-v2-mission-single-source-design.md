<!-- markdownlint-disable-file MAX_LINES -->

# V2 Mission Single-Source and Legacy V1 Retirement Design

**Issue:** #149

## Purpose

Make hierarchical v2 mission legs the single operational source of truth for
mission activation, route association, generated operational POIs, and
mission-bound POI active status. Retire the unused legacy v1 mission API and
runtime so the application cannot again show a route as active while Overview
cannot identify the associated mission POIs.

This follows a verified production regression: the React Mission screen writes
and activates v2 legs, while `GET /api/overview/upcoming-pois` currently reads
only legacy v1 activation state. The production deployment has an active route
but no v1 missions, causing the endpoint to return `no_active_route` and no
POIs.

## Decision

Remove the v1 mission runtime and API in this delivery. Do not delete flat v1
mission files from persisted volumes.

The application does not provide a supported migration from a flat v1
`MissionLeg` record to a hierarchical v2 `Mission`, because a safe conversion
requires a parent mission identity, a leg identity, and validation of the
route/transport inputs. Silently inventing those values would create a second
form of bad operational state.

Existing flat files under `data/missions/*.json` and their checksum/timeline
companions remain inert backup material. The implementation neither reads,
modifies, migrates, nor deletes them. Operators may archive or remove them only
through a separately approved data-retention procedure after confirming they
are no longer needed for rollback or forensic recovery.

## Scope

### In scope

- Resolve the globally active v2 mission leg and parent mission from persisted
  v2 mission storage.
- Make v2 leg activation globally exclusive across all parent missions.
- Use the active v2 context for Overview upcoming-POI projection and generic
  mission-bound POI active-status checks.
- Retire legacy `/api/missions` routes, v1 activation state, v1 CRUD and
  timeline operations, and flat v1 storage helpers that have no remaining
  consumer.
- Retain active route behavior, route-aware ETA semantics, trusted
  `mission-timeline` POI provenance, and all existing Overview map/table
  lifecycle rules.
- Make unavailable-state copy distinguish no active v2 mission leg from a
  missing/mismatched active route.
- Update API/operator documentation to state that only v2 mission-leg
  activation creates active mission context.

### Out of scope

- Deleting or transforming flat v1 mission files in any volume.
- Changing route CRUD, route import, route-only activation, flight-state
  calculation, or telemetry simulation contracts.
- Rendering generic/manual POIs in the Overview operational panel.
- Changing POI timing, urgency colors, Top 5 ordering, marker retention, or
  Grafana behavior.
- Adding a new migration UI, a legacy API compatibility shim, or an automatic
  conversion from v1 records to v2 missions.

## Current Failure and Required Invariant

The current system has two activation domains:

1. The React UI calls `POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate`.
   It persists `MissionLeg.is_active`, activates that leg's route, and builds a
   timeline using the parent mission ID for generated POIs.
2. Legacy Overview code calls v1 `get_active_mission_id()` and loads flat v1
   records from `/api/missions`. It cannot see the v2 active leg.

After this work, the following invariant holds:

> Every supported active mission is one persisted v2 leg. Its parent mission,
> leg ID, route ID, and active `ParsedRoute` are resolved together before a
> mission-scoped consumer performs work.

A route may still be active without an active v2 leg when it was deliberately
activated through route-only controls. That is not an active mission context;
mission-scoped Overview POIs must not be fabricated from it.

## Active V2 Mission Context

Introduce one backend resolver with a narrow, typed result, conceptually:

```text
ActiveMissionLegContext
  parent_mission_id: str
  parent_mission: Mission
  leg: MissionLeg
  route_id: str
  route: ParsedRoute
```

The resolver is the only supported way to discover active mission context.
It loads persisted v2 parent missions and their legs, identifies active legs,
and validates the route relationship against `RouteManager`.

### Resolution rules

1. **No active v2 leg**
   - Return no active mission context.
   - Do not infer a mission from the currently active route, POI labels, or
     legacy flat files.
2. **Exactly one active v2 leg with a non-empty route ID**
   - Load the route by the leg's route ID.
   - Require that it exists and is the `RouteManager` active route.
   - Return the complete context only after both checks succeed.
3. **An active leg has no route ID, route is unavailable, or its route differs
   from the active route**
   - Return a distinct route-context failure, with no POIs.
   - Log parent mission ID, leg ID, expected route ID, and observed active route
     ID without logging telemetry or unrelated mission contents.
4. **More than one active v2 leg exists**
   - Treat this as persisted state corruption, not a selection opportunity.
   - Return an explicit inconsistent-active-mission state with no POIs.
   - Emit a high-signal operator log identifying only parent/leg IDs.
   - Do not select an arbitrary leg.

The resolver may read the persisted v2 flags on each request. This preserves
correct state after a service restart and avoids another in-memory activation
source. A later cache is allowed only if it is invalidated by every v2 leg
write and still revalidates persistence before use.

## V2 Activation Lifecycle

`POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate` becomes the sole
supported mission activation command.

### Global exclusivity

Activation must make the selected leg the only active v2 leg across every
parent mission, not only among sibling legs in one parent mission. The write
uses a repository-wide active-leg lock in `data/missions/` so concurrent
requests cannot leave two persisted active legs.

Within that lock, the operation must:

1. Load the target parent mission and validate that the target leg exists.
2. Validate that the leg has a route ID and that `RouteManager` can load it.
3. Load every v2 mission, clear `is_active` from every other active leg, and
   set it on the target leg.
4. Persist every changed parent mission.
5. Activate the target route in `RouteManager`.
6. Rebuild and persist the target leg timeline with `parent_mission_id` equal
   to the v2 parent mission ID. Generated POIs retain
   `generated_source="mission-timeline"`.
7. Reset/apply existing flight and operational-clock state only after the v2
   mission context is durably valid.

If route activation or timeline construction fails, the endpoint must not
return a false activation success. It must restore the persisted active-leg
flags to their prior values before responding with a failure. The route
manager must not be left pointing at a route whose v2 leg was not successfully
activated.

Deactivation clears every active leg within the specified v2 parent mission
only when that parent owns the globally active leg; it deactivates the matching
route and existing mission-clock context. A request against a parent with no
active leg is idempotent and must not affect an active leg belonging to another
parent.

## Overview Upcoming-POI Contract

`GET /api/overview/upcoming-pois` remains the public endpoint and retains its
existing POI record fields, dynamic ETA behavior, ordering, Top 5 cap, and map
retention behavior. Its source context changes from v1 to the active v2 context.

The endpoint must:

1. Resolve `ActiveMissionLegContext`.
2. Load POIs using `mission_id=context.parent_mission_id`.
3. Admit only records with a non-null `kind` and trusted
   `generated_source="mission-timeline"`.
4. Calculate anticipated/estimated ETA against `context.route`, exactly as
   before. In-flight ETA still requires live position, speed, and active-route
   geometry; it is never a scheduled-clock fallback.
5. Return no marker/table records if context resolution fails.

### Top-level states

Replace the ambiguous `no_active_route` outcome with explicit states:

- `no_active_mission` — no v2 leg is active; a route-only active route does not
  qualify.
- `route_unavailable` — an active leg exists, but has no usable route or does
  not match the active `RouteManager` route.
- `inconsistent_active_mission` — more than one v2 leg is persisted active.
- `no_generated_pois` — valid active v2 context exists but no trusted generated
  POIs exist for the parent mission.
- `no_upcoming_pois` — trusted generated records exist but none is table-upcoming.
- `unavailable` — required in-flight telemetry is unavailable.
- `available` — at least one generated POI is upcoming.

The React panel maps these states to truthful compact copy. `no_active_mission`
must not say “No active route.” `route_unavailable` must explain that the
active mission leg is not bound to the active route. It must not expose raw IDs
in the user-facing panel.

## Other Mission-Bound POI Consumers

The generic POI active-status helper currently loads flat v1 missions when a
POI has `mission_id`. Replace that lookup with `ActiveMissionLegContext`:

- A mission-bound POI is active when its `mission_id` equals the active v2
  parent mission ID and, when it has `route_id`, that route equals the active
  v2 leg route ID.
- A route-bound POI without a mission ID keeps its current active-route rule.
- A global POI remains active.
- No active/inconsistent/mismatched v2 context means mission-bound POIs are
  inactive; do not fall back to v1 data.

This preserves the distinct behavior of manual/global POIs while removing the
last production dependency on the legacy mission model.

## Legacy V1 Retirement

Remove from the running application:

- the `/api/missions` v1 router and all of its activation, CRUD, timeline,
  export, and satellite endpoints;
- the v1 in-memory active-mission ID and its startup/recovery behavior;
- the v1 `MissionLeg` persistence functions, checksums, flat-file discovery,
  and unreferenced timeline path variants;
- v1 route modules and their dedicated unit/integration tests;
- v1 API documentation and references.

The retired paths are absent from the router and return normal `404 Not Found`.
They must not redirect, proxy, or silently translate requests into v2 calls.
That makes unsupported-client use detectable instead of preserving another
hidden state path.

Keep shared v2 storage primitives, including mission directory access, v2
leg timelines, locks, and `MissionLeg` as the v2 child model. Remove only code
whose remaining purpose is the flat v1 API/storage model.

Before deleting a shared helper, search all production imports and either move
the consumer to a v2 equivalent or retain the helper as a clearly v2-owned
primitive. Test-only import references do not justify preserving a retired
runtime path.

## Data and Deployment Safety

- The change is a code/API retirement, not a volume cleanup.
- Docker volumes remain retained. No `rm`, directory cleanup, or startup
  migration touches `data/missions/*.json`, `*.sha256`, or old flat timeline
  files.
- The application starts normally when flat v1 artifacts exist alongside v2
  directories; v2 discovery ignores non-directory entries.
- Existing v2 missions and legs are loaded without rewrites until an operator
  changes them through a v2 endpoint.
- Deployment/restart acceptance must demonstrate that persisted active v2 leg
  state resolves after process restart, without requiring an operator to
  reactivate the leg.
- Release/operator notes must call out the deliberate breaking removal of
  `/api/missions` and the retained-but-inert v1 files.

## Failure Handling and Observability

- Activation returns a non-2xx response on invalid route, failed route
  activation, failed timeline construction, or failed rollback. It never
  reports success with an unresolvable active context.
- Overview preserves unrelated globe layers when its context state is not
  `available`.
- Backend logs record state transitions and context identifiers, not position,
  speed, credentials, or mission payloads.
- The active-v2 resolver must have focused diagnostics for no active leg,
  route mismatch, and multiple active legs. These diagnostics distinguish
  configuration errors from a service defect.

## Verification

### Backend unit and integration tests

1. Create a v2 parent mission/leg with a route, activate it, and prove the
   resolver returns its parent ID, leg, and active route after a fresh resolver
   instance/restart simulation.
2. Activate a v2 leg and prove `/api/overview/upcoming-pois` returns trusted
   generated departure/arrival and timeline POIs for the v2 parent mission.
   No v1 mission fixture or monkeypatch may supply active context.
3. Cover no active leg, no route ID, missing route, active-route mismatch, and
   multiple persisted active legs. Each returns its explicit state and no POIs.
4. Prove activating a leg in one parent clears an active leg in another parent
   under the global lock; prove a failure rolls back persisted active flags and
   does not report success.
5. Preserve current ETA coverage: late departure, speed change, route detour,
   missing telemetry, lifecycle filtering, dynamic ordering, and 60-minute
   retention all run through v2 context.
6. Prove trusted generated POIs use the parent v2 mission ID and manual typed
   POIs remain excluded from Overview but survive regeneration.
7. Prove generic mission-bound POI active status follows v2 parent/leg context,
   while route-only and global POI rules remain unchanged.
8. Assert every former `/api/missions` v1 route is absent (404) and v2 routes
   remain available.
9. Place representative flat v1 JSON/checksum/timeline artifacts beside v2
   directories, start the application, and prove they remain byte-for-byte
   unchanged while v2 activation and Overview work.

### Frontend and browser tests

1. Update Overview fixtures to use `no_active_mission`, `route_unavailable`,
   and `inconsistent_active_mission` copy; ensure they do not claim no route
   when an active route may exist.
2. Preserve all existing Upcoming POI table/marker and label-layout coverage.
3. Add browser coverage that activates a v2 mission leg through the same API
   used by the Mission screen, then observes generated POIs on Overview.
4. Run exact Chromium acceptance at 1920×1080 on the implementation SHA. It
   must prove the active v2 mission renders retained stars and the non-scrollable
   Top 5 panel.

### Required delivery gates

- Fresh backend full suite, frontend lint/unit/build, CI formatting checks, and
  exact 1920×1080 Chromium acceptance.
- Independent task review and whole-branch review.
- Live deployment proof must query `/api/v2/missions`, the active v2 leg,
  `/api/flight-status`, and `/api/overview/upcoming-pois` from the same
  deployment after activation. A browser-only visual claim is insufficient.

## Documentation Impact

Update the Overview API reference, Overview feature documentation, mission
operator/developer workflow, and release notes. Document v2 leg activation as
the sole supported active mission mechanism and list `/api/missions` removal
as a breaking API change. No Grafana dashboard change is required.
