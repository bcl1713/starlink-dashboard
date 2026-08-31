# React Operations Overview Plan Map

> **For Hermes:** This document supersedes the stale exact-file-map wording for
> later map and composition work. Preserve completed prior-phase inventory as
> historical executed paths, and preserve each owning task's TDD order and
> commit boundary.

## Binding Rules

Exact paths remain binding only where they were already implemented in prior
tasks or where an owning contract explicitly names a public API, route, module,
or asset path. For new operational-map and responsive-composition work, the
binding unit is the responsibility contract, not a hard file count.

Likely paths named below are ownership examples and advisory starting points.
Implementation may add focused modules, colocated tests, fixtures, or styles
when cohesion requires it. Do not pack unrelated behavior into a file merely to
avoid creating another file.

The repository's 300 physical-line maximum is a cohesion and maintainability
guard for production and test files. It is not permission to create dense
multi-responsibility files, and it is not a requirement to minimize file count.

Planning artifacts may keep task and phase headings. Production source and test
identifiers introduced by this work must use domain names, not implementation
phase labels.

Repository-local contracts refine the Task 11 and Task 12 implementation work:

- [Task 11 responsibility map](#task-11-responsibility-map)
- [Task 11 binding contract](#task-11-binding-contract)
- [Task 12 responsibility map](#task-12-responsibility-map)
- [Task 12 binding contract](#task-12-binding-contract)

## Historical Executed Inventory

### Backend and Contract Tests

- Create: `backend/starlink-location/app/models/monitoring.py`
- Create: `backend/starlink-location/app/services/prometheus_client.py`
- Create: `backend/starlink-location/app/api/monitoring.py`
- Modify: `backend/starlink-location/app/api/weather.py`
- Modify: `backend/starlink-location/app/services/weather_radar.py`
- Modify: `backend/starlink-location/app/models/poi.py`
- Modify: `backend/starlink-location/app/api/pois/etas.py`
- Modify: `backend/starlink-location/app/api/active_x_link.py`
- Modify: `backend/starlink-location/app/api/geojson.py`
- Modify: `backend/starlink-location/app/services/ground_entry_point.py`
- Modify: `backend/starlink-location/main.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_models.py`
- Create: `backend/starlink-location/tests/unit/test_prometheus_client.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_api.py`
- Modify: `backend/starlink-location/tests/unit/test_weather_api.py`
- Modify: `backend/starlink-location/tests/unit/test_poi_eta_models.py`
- Modify: `backend/starlink-location/tests/unit/test_active_x_link.py`
- Modify: `backend/starlink-location/tests/unit/test_ground_entry_point.py`
- Create: `backend/starlink-location/tests/unit/test_geojson_freshness.py`
- Create: `tools/tests/test_mission_planner_nginx.py`

### Frontend and Browser Tests

- Modify: `frontend/mission-planner/package.json`
- Modify: `frontend/mission-planner/package-lock.json`
- Create: `frontend/mission-planner/vitest.config.ts`
- Create: `frontend/mission-planner/src/test/setup.ts`
- Create: `frontend/mission-planner/src/test/render-smoke.test.tsx`
- Modify: `frontend/mission-planner/src/App.tsx`
- Modify: `frontend/mission-planner/src/index.css`
- Modify: `frontend/mission-planner/nginx.conf`
- Create: `frontend/mission-planner/src/types/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.test.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewGrid.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewControls.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/WorldClocks.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ClockSettings.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OperationalMap.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/LayerDisclosure.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/POIQuickReference.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricChart.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricSummary.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ObstructionGauge.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/GroundEntryPointCard.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/useOverviewData.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/preferences.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/history.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/geometry.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/formatters.ts`
- Create colocated pure/component tests as `*.test.ts(x)`.
- Create/modify: `frontend/mission-planner/tests/e2e/overview.spec.ts`
- Create/modify:
  `frontend/mission-planner/tests/e2e/overview-continuity.spec.ts`
- Create/modify: `frontend/mission-planner/tests/e2e/fixtures/overview.ts`
- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`

### CI and Documentation

- Modify: `.github/workflows/lint.yml`
- Modify: `tools/tests/test_link_checker_config.py`
- Modify: `.env.example`
- Modify the exact documentation paths listed in Phase 4 after independent docs
  routing; do not fold those changes into core feature commits.

This inventory records the original planned and already executed path surface.
For Tasks 11-12, it is superseded by the responsibility maps below where the old
list promised monolithic files such as `OverviewPage/OperationalMap.tsx`.

## Task 11 Responsibility Map

Task 11 owns the operational map with all layers. It must implement the public
`OperationalMap` shell and handle contract from the approved handoff, including
stable `MapContainer` ownership, `fitToAvailableLayers()`, `focusCoordinates()`,
and `getMap()` for diagnostics only.

Responsibilities:

- Leaflet lifecycle and identity: create the map, basemap, panes, controls,
  radar layer, and vector layer groups once; mutate existing instances during
  refresh; preserve viewport, selected feature, disclosure, measurement, and
  mobile interaction state.
- Vector projection and reconciliation: use the Task 7 IDL utilities, split
  route-like geometries without cross-segment lines, validate finite
  coordinates, and keep stable history feature IDs through split, merge, and
  rolling-window changes.
- Eleven vector `LayerGroup` identities: planned-route west/east, active-link
  normal/warning, position-history west/east, flight-route markers, satellites,
  mission events, ground entry point, and current position.
- Radar `GridLayer`: fetch only same-origin tile bytes through the Task 6
  service path, enforce bounded in-flight and tracked records, coalesce visible
  tile requests, retain last-good visible tiles, revoke object URLs, and report
  one result per visible generation using the conservative frame timestamp.
- Layer disclosure, controls, and accessibility: expose the exact ordered twelve
  operational layers, radar toggle/retry, fit, zoom, scale, measurement, feature
  details, textual equivalent, mobile interaction opt-in, keyboard operation,
  focus styling, and 44 px touch targets.
- Map fixtures and tests: cover contract order/styles, map and layer identity,
  feature reconciliation, IDL/hemisphere behavior, fit rules, radar lifecycle,
  object-URL cleanup, controls, textual equivalents, reduced motion, and
  repeated mount/unmount cleanup.

Likely production ownership examples include
`frontend/mission-planner/src/pages/OverviewPage/OperationalMap/` modules for
the public shell, contracts, feature building, geometry composition, stable map
hooks, vector layers, radar grid/tile management, controls, disclosure, details,
summary, local map CSS, and local marker assets under
`public/assets/overview-map/`. These paths are advisory unless a public import,
asset URL, or test contract explicitly makes one binding.

Task 11 must honor the approved props, CSP, history-ID, radar, map-interaction,
and ref ownership contracts in the
[Task 11 binding contract](#task-11-binding-contract) without expanding product
scope.

### Task 11 Binding Contract

Activation-critical ownership clauses:

- `OperationalMap` is the public shell. It owns the stable Leaflet composition
  and exposes only the approved handle, including `focusCoordinates()` for Task
  12 and `getMap()` for diagnostics.
- Task 11 owns a single timestamp/history identity reconciliation path for map
  features, including IDL split/merge behavior and rolling-window updates.
- Task 11 owns the eleven vector groups plus the radar `GridLayer`: planned
  route west/east, active link normal/warning, position history west/east,
  flight-route markers, satellites, mission events, ground entry point, current
  position, and same-origin radar tiles.
- Radar retry and preference state are controlled by approved callbacks/props.
  `LayerDisclosure` is the sole radar and layer-control surface.
- Object URLs stay internal to radar tile management and must be revoked.
  Nginx/browser CSP adds only `blob:` to `img-src` as needed for those object
  URLs, leaves `connect-src` unchanged, adds no direct RainViewer browser origin
  or network access, and remains subject to later exact-head real-browser
  CSP/network acceptance.
- Task 11 owns responsive map interaction behavior, including mobile interaction
  opt-in, keyboard operation, reduced motion, textual equivalents, and stable
  state across refreshes and remounts.

## Task 12 Responsibility Map

Task 12 owns responsive composition, routing, fullscreen, and page-level
accessibility for one continuously mounted Overview tree. Responsive changes,
rotation, refresh, and fullscreen must not choose between separate desktop and
mobile component trees.

Responsibilities:

- Overview page/controller wiring: `OverviewPage` owns preferences, Task 9 data
  orchestration, the shared clock, the single live region, fullscreen mode, and
  top-level composition. Panel retry callbacks use `controller.manualRefresh`.
- Map ref ownership: Task 12 may call only the Task 11 `focusCoordinates()`
  handle for GEP focus. It must not import Leaflet or call `getMap()`,
  `setView()`, `flyTo()`, `panTo()`, or `fitBounds()`.
- Responsive layout and styles: `OverviewGrid` owns placement semantics while
  Task 12 owns `.overview-map-region` height at every accepted viewport and
  fullscreen/kiosk state. `OperationalMap` fills that region without imposing
  composed viewport clamps or page overflow rules.
- Controls and disclosure ownership: `OverviewControls` owns refresh cadence,
  manual refresh, POI filter, and clock settings. `LayerDisclosure` remains the
  only radar and layer-control owner. Chart panels keep their own history-table
  disclosures mounted.
- Accessibility: preserve one `main`, skip link, logical headings, visible
  focus, reduced motion, one polite live region sourced only from
  `snapshot.announcement`, and no one-second live spam.
- Composition tests: cover routing/history, navigation order and `aria-current`,
  fixed semantic order, responsive layout modes, fullscreen entry/exit/fallback,
  state preservation, overflow rules, map-height contract, and accessibility.
- Later browser acceptance: Tasks 13-14 prove six accepted viewports, actual
  Leaflet behavior, touch/page scroll, fullscreen, CSP, same-origin radar,
  rendered map assets, and Grafana parity on the exact tested head.

Likely production ownership examples include
`frontend/mission-planner/src/pages/OverviewPage.tsx`,
`frontend/mission-planner/src/pages/OverviewPage/OverviewGrid.tsx`, focused
colocated tests, `frontend/mission-planner/src/App.tsx`, and
`frontend/mission-planner/src/index.css`. These paths are advisory except where
the routing, exported shell boundaries, or CSS class contracts in the approved
handoff explicitly require them.

Task 12 must honor the approved props, height, fullscreen, accessibility,
radar-control, map-ref, and responsive-composition contracts in the
[Task 12 binding contract](#task-12-binding-contract) without expanding product
scope.

### Task 12 Binding Contract

Activation-critical ownership clauses:

- Task 12 owns one mounted Overview composition tree across desktop, mobile,
  rotation, refresh, and fullscreen states. It must not switch between separate
  desktop and mobile component trees.
- Task 12 owns `.overview-map-region` height at every accepted viewport and
  fullscreen/kiosk state. `OperationalMap` must fill that region at 100% height
  and width.
- Task 12 may focus map content only through the Task 11 `focusCoordinates()`
  handle. It must not import Leaflet or call map viewport methods directly.
- `OverviewControls` owns refresh cadence, manual refresh, POI filter, clock
  settings, and controlled radar preference plumbing. `LayerDisclosure` remains
  the sole radar and layer-control UI.
- Task 12 owns responsive page interaction behavior: scroll containment,
  touch/page-scroll coexistence, fullscreen focus restoration, navigation order,
  live-region discipline, and state preservation.
- Browser acceptance remains later Task 13-14 work and must prove the mounted
  tree, map height, real Leaflet behavior, same-origin radar, CSP behavior,
  responsive interaction, and rendered assets on the exact tested head.
