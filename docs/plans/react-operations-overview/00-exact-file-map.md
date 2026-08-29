# React Operations Overview Exact File Map

> **For Hermes:** This inventory is binding for the master plan and Phases 1–3.
> Preserve the owning task's TDD order and commit boundary for every path.

## Backend and contract tests

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

## Frontend and browser tests

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

## CI and documentation

- Modify: `.github/workflows/lint.yml`
- Modify: `tools/tests/test_link_checker_config.py`
- Modify: `.env.example`
- Modify the exact documentation paths listed in Phase 4 after independent docs
  routing; do not fold those changes into core feature commits.

Keep production TypeScript files near or below the repository's 300-line target;
split components rather than creating a monolithic dashboard page.
