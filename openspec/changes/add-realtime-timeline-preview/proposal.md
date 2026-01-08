# Change: Real-Time Timeline Preview During Mission Planning

## Why

Currently, users must save mission leg configurations and navigate to the export
phase to see satellite transitions, outages, and X-band/Ku conflicts visualized
on the timeline. This creates a slow feedback loop that hinders iterative
mission planning. Users need to see the effects of their configuration changes
in real-time to make informed decisions about satellite transitions and outage
windows.

## What Changes

- Add backend preview API endpoint that calculates timelines without persisting
  to disk
- Create debounced frontend hook that triggers timeline calculations as users
  type/modify configurations
- Display color-coded route map showing NOMINAL (green), DEGRADED (yellow), and
  CRITICAL (red) communication status segments
- Add timeline table component showing segment-by-segment details during
  planning phase
- Implement dual-state management separating saved timelines from preview
  timelines
- Include route samples (lat/lon + timestamp) in preview response for accurate
  map rendering

## Impact

- **Affected specs:**
  - `timeline-preview` (NEW): Real-time timeline calculation and visualization
    capability
- **Affected code:**
  - Backend:
    - `backend/starlink-location/app/mission/routes_v2.py` - Add preview
      endpoint
    - `backend/starlink-location/app/mission/models.py` - Add samples field to
      timeline model
    - `backend/starlink-location/app/mission/timeline_service.py` - Support
      optional sample inclusion
  - Frontend:
    - `frontend/mission-planner/src/services/timeline.ts` - Add preview API
      client
    - `frontend/mission-planner/src/hooks/api/useTimelinePreview.ts` (NEW) -
      Debounced preview hook
    - `frontend/mission-planner/src/components/timeline/TimelineTable.tsx`
      (NEW) - Timeline table component
    - `frontend/mission-planner/src/components/common/RouteMap/ColorCodedRoute.tsx`
      (NEW) - Color-coded map layer
    - `frontend/mission-planner/src/components/common/RouteMap.tsx` - Integrate
      timeline segments
    - `frontend/mission-planner/src/pages/LegDetailPage.tsx` - Orchestrate
      preview state
    - `frontend/mission-planner/src/pages/LegDetailPage/TimelinePreviewSection.tsx`
      (NEW) - Preview container
- **Performance impact:**
  - Backend: Additional API requests (~1 request per 500ms when user is actively
    editing)
  - Response time: <500ms for typical routes (300 waypoints, 60s sample
    interval)
  - Frontend: Real-time map re-rendering with colored segments
- **User experience improvement:**
  - Immediate feedback on configuration changes
  - Reduced need to iterate through save/export cycle
  - Better understanding of satellite transition impacts
