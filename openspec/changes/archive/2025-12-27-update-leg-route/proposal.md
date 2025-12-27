# Change: Update Leg Route via KML Upload

## Why

In the weeks leading up to a mission, routes frequently change due to updated timing, waypoint adjustments, or slight path modifications that don't require satellite planning changes. Currently, users must delete the entire leg and recreate it from scratch to update a route, losing all satellite transition configurations, outage schedules, AAR windows, and manually configured transport settings. This workflow is tedious, error-prone, and frustrating for mission planners.

## What Changes

- Add a new API endpoint `PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route` that accepts a KML file upload
- Preserve satellite transition configurations and outage schedules across route updates
- Validate and preserve AAR windows if the new route contains matching waypoint names; remove AAR windows that reference waypoints no longer present in the updated route
- Update only the route geometry, waypoints, and derived timing data
- Automatically regenerate timeline with the new route while maintaining satellite planning
- Delete and re-import POIs from the new KML waypoint placemarks
- Update route map visualizations with the new route path
- Provide clear feedback to users if AAR windows were removed due to missing waypoints
- Provide frontend UI to upload replacement KML files from the leg detail page

## Impact

- **Affected specs:** `mission-export` (existing capability covering mission/leg operations and timeline generation)
- **Affected code:**
  - Backend: `backend/starlink-location/app/mission/routes_v2.py` (new route update endpoint)
  - Backend: `backend/starlink-location/app/api/routes/upload.py` (reuse KML parsing logic)
  - Backend: `backend/starlink-location/app/mission/timeline_service.py` (timeline regeneration)
  - Frontend: `frontend/mission-planner/src/pages/LegDetailPage.tsx` (upload UI)
  - Frontend: `frontend/mission-planner/src/services/missions.ts` (API client method)
- **User workflow:** Mission planners can update leg routes in-place without losing satellite configuration, reducing planning time from minutes to seconds. If AAR windows become invalid due to missing waypoints, users receive clear notification and must reconfigure them.
- **Breaking changes:** None - this is purely additive functionality
