# Implementation Tasks

## 1. Backend: Route Update Endpoint

- [x] 1.1 Add `PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route` endpoint in `backend/starlink-location/app/mission/routes_v2.py`
- [x] 1.2 Accept multipart/form-data KML file upload with file validation (.kml extension only)
- [x] 1.3 Load existing mission and leg using `load_mission_v2()` and validate existence
- [x] 1.4 Parse uploaded KML file using existing `parse_kml_file()` from `app/services/kml_parser`
- [x] 1.5 Store new KML file to disk in routes directory with unique filename handling
- [x] 1.6 Delete old route file from disk if it exists
- [x] 1.7 Update leg's `route_id` field to match new route filename stem
- [x] 1.8 Validate AAR windows against new route waypoint names and collect removed windows
- [x] 1.9 Update leg's AAR windows configuration, removing invalid entries
- [x] 1.10 Delete existing POIs associated with old route_id using `poi_manager.delete_route_pois()`
- [x] 1.11 Import new POIs from KML waypoint placemarks using `_import_waypoints_as_pois()`
- [x] 1.12 Regenerate timeline using `build_mission_timeline()` with new route
- [x] 1.13 Save updated mission using `save_mission_v2()`
- [x] 1.14 Save regenerated timeline using `save_mission_timeline()`
- [x] 1.15 Return updated leg with warnings array if AAR windows were removed
- [x] 1.16 Add proper error handling for file I/O, KML parsing, and timeline generation failures
- [x] 1.17 Add rate limiting (10/minute) to prevent abuse

## 2. Backend: Helper Function for AAR Validation

- [x] 2.1 Create helper function `_validate_aar_windows_against_route()` in `routes_v2.py`
- [x] 2.2 Accept AAR window list and parsed route as parameters
- [x] 2.3 Extract waypoint names from parsed route waypoints
- [x] 2.4 Check each AAR window for referenced waypoint existence
- [x] 2.5 Return tuple of (valid_aar_windows, removed_waypoint_names)
- [x] 2.6 Add logging for removed AAR windows with waypoint details

## 3. Backend: Route Manager Cache Update

- [x] 3.1 Update route manager's internal cache to remove old route_id
- [x] 3.2 Add new route to route manager cache with new route_id
- [x] 3.3 Ensure watchdog file observer picks up new route file
- [x] 3.4 Test cache consistency after route replacement

## 4. Frontend: TypeScript Types

- [x] 4.1 Add `UpdateLegRouteResponse` interface in `frontend/mission-planner/src/types/mission.ts`
- [x] 4.2 Include `leg: MissionLeg` and `warnings?: string[]` fields in response type
- [x] 4.3 Ensure type compatibility with existing MissionLeg interface

## 5. Frontend: API Client Method

- [x] 5.1 Add `updateLegRoute(missionId: string, legId: string, kmlFile: File)` method to `frontend/mission-planner/src/services/missions.ts`
- [x] 5.2 Use FormData to encode KML file for multipart/form-data request
- [x] 5.3 Send PUT request to `/api/v2/missions/{missionId}/legs/{legId}/route`
- [x] 5.4 Return typed response as `Promise<UpdateLegRouteResponse>`
- [x] 5.5 Add error handling for network failures and API errors

## 6. Frontend: React Query Hook

- [x] 6.1 Create `useUpdateLegRoute()` hook in `frontend/mission-planner/src/hooks/api/useMissions.ts`
- [x] 6.2 Use `useMutation` from TanStack React Query
- [x] 6.3 Invalidate mission cache on success using `queryClient.invalidateQueries(['missions', missionId])`
- [x] 6.4 Invalidate missions list cache on success
- [x] 6.5 Return mutation state (loading, error, success) for UI feedback

## 7. Frontend: Update Route UI Component

- [x] 7.1 Add "Update Route" button to leg detail page in `frontend/mission-planner/src/pages/LegDetailPage/LegHeader.tsx`
- [x] 7.2 Create file input that accepts only `.kml` files
- [x] 7.3 Add file selection handler to validate file extension client-side
- [x] 7.4 Show current route filename near the update button
- [x] 7.5 Display loading spinner during upload using mutation state
- [x] 7.6 Show success alert notification on successful upload
- [x] 7.7 Display warning alert if API returns warnings about removed AAR windows
- [x] 7.8 Show error alert if upload fails with user-friendly error message
- [x] 7.9 Disable upload button while upload is in progress

## 8. Frontend: Route Map Refresh

- [x] 8.1 Ensure RouteMap component refreshes when leg data is invalidated (automatic via React Query)
- [x] 8.2 Verify map displays new route path after successful upload (automatic via React Query)
- [x] 8.3 Test that POI markers update to reflect new waypoints (automatic via React Query)

## 9. Frontend: Timeline Table Refresh

- [x] 9.1 Ensure timeline table component re-fetches data after route update (automatic via React Query)
- [x] 9.2 Verify timeline displays updated timing data based on new route (automatic via React Query)

## 10. Testing: Backend Unit Tests

- [ ] 10.1 Write test for successful route update with compatible AAR windows
- [ ] 10.2 Write test for route update that removes AAR windows due to missing waypoints
- [ ] 10.3 Write test for mission not found error (404)
- [ ] 10.4 Write test for leg not found error (404)
- [ ] 10.5 Write test for invalid KML file error (400)
- [ ] 10.6 Write test for route file replacement on disk
- [ ] 10.7 Write test for timeline regeneration after route update
- [ ] 10.8 Write test for POI deletion and re-import
- [ ] 10.9 Write test for route manager cache update

## 11. Testing: Frontend Integration Tests

- [ ] 11.1 Write Playwright test for successful route upload workflow
- [ ] 11.2 Write test for file validation (reject non-.kml files)
- [ ] 11.3 Write test for warning display when AAR windows removed
- [ ] 11.4 Write test for error handling on upload failure
- [ ] 11.5 Verify route map and timeline refresh after upload

## 12. Documentation

- [ ] 12.1 Update API documentation for new `PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route` endpoint
- [ ] 12.2 Document AAR window validation behavior in user guide
- [ ] 12.3 Add example curl command for route update
- [ ] 12.4 Update frontend component documentation

## 13. Validation and Smoke Testing

- [ ] 13.1 Test complete workflow: create leg, update route multiple times, verify timeline accuracy
- [ ] 13.2 Test with various KML file sizes and complexities
- [ ] 13.3 Verify satellite transitions and outages persist correctly across updates
- [ ] 13.4 Test AAR window preservation and removal scenarios
- [ ] 13.5 Verify old route files are properly deleted from disk
- [ ] 13.6 Test concurrent route updates (file locking)
- [ ] 13.7 Run backend Docker rebuild and verify endpoint availability
- [ ] 13.8 Run frontend build and verify no TypeScript errors
