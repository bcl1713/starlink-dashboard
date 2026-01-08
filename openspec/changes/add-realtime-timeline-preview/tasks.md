# Implementation Tasks

**Branch:** `feature/add-realtime-timeline-preview`

**Commit Strategy:** Make small, atomic commits after each logical milestone. Each
commit should be independently testable.

## 0. Setup

- [ ] 0.1 Create feature branch: `git checkout -b feature/add-realtime-timeline-preview`
- [ ] 0.2 Commit initial OpenSpec proposal files
  - **Commit:** `docs: add openspec proposal for realtime timeline preview`

## 1. Backend Preview API

- [ ] 1.1 Add `LegTimelinePreviewRequest` Pydantic model in `routes_v2.py`
- [ ] 1.2 Create `POST /api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview`
      endpoint
- [ ] 1.3 Implement endpoint handler that reuses `build_mission_timeline()` without
      disk writes
- [ ] 1.4 Test preview endpoint with curl/Postman (verify no files created)
- [ ] 1.5 **COMMIT:** `feat: add timeline preview API endpoint`
- [ ] 1.6 Add optional `samples` field to `MissionLegTimeline` model in `models.py`
- [ ] 1.7 Modify `timeline_service.py::build_mission_timeline()` to support
      `include_samples` parameter
- [ ] 1.8 Test preview endpoint returns samples correctly
- [ ] 1.9 **COMMIT:** `feat: include route samples in timeline preview response`

## 2. Frontend Preview Service & Hook

- [ ] 2.1 Add `TimelinePreviewRequest` interface to `types/timeline.ts`
- [ ] 2.2 Add `previewTimeline()` function to `services/timeline.ts`
- [ ] 2.3 **COMMIT:** `feat: add timeline preview API client service`
- [ ] 2.4 Create `useTimelinePreview.ts` hook with 500ms debouncing
- [ ] 2.5 Implement request cancellation via AbortController
- [ ] 2.6 Add loading state and error handling
- [ ] 2.7 Test hook with rapid config changes (verify debouncing)
- [ ] 2.8 **COMMIT:** `feat: add debounced timeline preview hook`

## 3. Timeline Table Component

- [ ] 3.1 Create `components/timeline/TimelineTable.tsx` with color-coded status
      badges
- [ ] 3.2 Implement table columns: Segment #, Status, Times, Duration, Transport
      States, Reasons
- [ ] 3.3 Test table with sample timeline data
- [ ] 3.4 **COMMIT:** `feat: add timeline table component with color-coded status`
- [ ] 3.5 Add virtualization for large timelines (>200 segments)
- [ ] 3.6 Test with large dataset (300+ segments)
- [ ] 3.7 **COMMIT:** `feat: add virtualization for large timeline tables`
- [ ] 3.8 Create `pages/LegDetailPage/TimelinePreviewSection.tsx` collapsible
      container
- [ ] 3.9 Add "Unsaved" badge indicator when preview differs from saved state
- [ ] 3.10 **COMMIT:** `feat: add timeline preview section with unsaved indicator`

## 4. Color-Coded Route Map

- [ ] 4.1 Create `components/common/RouteMap/ColorCodedRoute.tsx` layer component
- [ ] 4.2 Implement temporal-to-spatial mapping (segment timestamps to coordinates)
- [ ] 4.3 Render Leaflet polylines with status-based colors (green/yellow/red)
- [ ] 4.4 Test with sample timeline data (verify colors match status)
- [ ] 4.5 **COMMIT:** `feat: add color-coded route layer for timeline visualization`
- [ ] 4.6 Modify `RouteMap.tsx` to accept `timelineSegments` and `routeSamples` props
- [ ] 4.7 Add map legend explaining color coding
- [ ] 4.8 Ensure proper layer ordering (colored segments below blue route line)
- [ ] 4.9 Test map updates when timeline changes
- [ ] 4.10 **COMMIT:** `feat: integrate color-coded timeline into route map`

## 5. LegDetailPage Integration

- [ ] 5.1 Integrate `useTimelinePreview` hook in `LegDetailPage.tsx`
- [ ] 5.2 Wire preview config from satellite/AAR state
- [ ] 5.3 Add `TimelinePreviewSection` below config tabs in left column
- [ ] 5.4 Test end-to-end flow (config change → preview → map update)
- [ ] 5.5 **COMMIT:** `feat: integrate timeline preview into leg detail page`
- [ ] 5.6 Pass preview timeline to `LegMapVisualization` component
- [ ] 5.7 Update `useLegData.ts` to track preview vs saved state
- [ ] 5.8 Add confirmation dialog for unsaved timeline changes
- [ ] 5.9 Test save/cancel/navigate scenarios with unsaved changes
- [ ] 5.10 **COMMIT:** `feat: add unsaved state management for timeline preview`

## 6. Testing & Validation

- [ ] 6.1 Test backend preview endpoint responds <500ms for typical routes
- [ ] 6.2 Verify no disk writes occur during preview calculations
- [ ] 6.3 Test frontend debouncing (verify only 1 request after 500ms idle)
- [ ] 6.4 Verify color-coded map renders correctly with sample data
- [ ] 6.5 Test timeline table displays all segments with correct data
- [ ] 6.6 Verify "Unsaved" indicator appears/disappears correctly
- [ ] 6.7 Test with complex routes (300+ waypoints, multiple transitions)
- [ ] 6.8 Verify UI remains responsive during calculations
- [ ] 6.9 Test error scenarios (network failures, invalid configs, missing routes)
- [ ] 6.10 **COMMIT:** `test: add comprehensive tests for timeline preview`

## 7. Documentation

- [ ] 7.1 Update API documentation with preview endpoint
- [ ] 7.2 Add JSDoc comments to new frontend hooks and components
- [ ] 7.3 Update user-facing documentation explaining real-time preview feature
- [ ] 7.4 **COMMIT:** `docs: add documentation for timeline preview feature`

## 8. Finalization

- [ ] 8.1 Run full test suite (frontend and backend)
- [ ] 8.2 Run linting and formatting checks
- [ ] 8.3 Rebuild Docker containers and verify functionality
- [ ] 8.4 Review all commits for clear messages and atomic changes
- [ ] 8.5 Push feature branch: `git push -u origin feature/add-realtime-timeline-preview`
- [ ] 8.6 Create pull request with link to OpenSpec proposal
- [ ] 8.7 Request code review
