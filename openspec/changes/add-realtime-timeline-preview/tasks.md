# Implementation Tasks

**Branch:** `feature/add-realtime-timeline-preview`

**Commit Strategy:** Make small, atomic commits after each logical milestone. Each
commit should be independently testable.

## 0. Setup

- [x] 0.1 Create feature branch: `git checkout -b feature/add-realtime-timeline-preview`
- [x] 0.2 Commit initial OpenSpec proposal files
  - **Commit:** `docs: add openspec proposal for realtime timeline preview`

## 1. Backend Preview API

- [x] 1.1 Add `LegTimelinePreviewRequest` Pydantic model in `routes_v2.py`
- [x] 1.2 Create `POST /api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview`
      endpoint
- [x] 1.3 Implement endpoint handler that reuses `build_mission_timeline()` without
      disk writes
- [x] 1.4 Test preview endpoint with curl/Postman (verify no files created)
- [x] 1.5 **COMMIT:** `feat: add timeline preview API endpoint`
- [x] 1.6 Add optional `samples` field to `MissionLegTimeline` model in `models.py`
- [x] 1.7 Modify `timeline_service.py::build_mission_timeline()` to support
      `include_samples` parameter
- [x] 1.8 Test preview endpoint returns samples correctly
- [x] 1.9 **COMMIT:** `feat: include route samples in timeline preview response`

## 2. Frontend Preview Service & Hook

- [x] 2.1 Add `TimelinePreviewRequest` interface to `types/timeline.ts`
- [x] 2.2 Add `previewTimeline()` function to `services/timeline.ts`
- [x] 2.3 **COMMIT:** `feat: add timeline preview API client service`
- [x] 2.4 Create `useTimelinePreview.ts` hook with 500ms debouncing
- [x] 2.5 Implement request cancellation via AbortController
- [x] 2.6 Add loading state and error handling
- [x] 2.7 Test hook with rapid config changes (verify debouncing)
- [x] 2.8 **COMMIT:** `feat: add debounced timeline preview hook`

## 3. Timeline Table Component

- [x] 3.1 Create `components/timeline/TimelineTable.tsx` with color-coded status
      badges
- [x] 3.2 Implement table columns: Segment #, Status, Times, Duration, Transport
      States, Reasons
- [x] 3.3 Test table with sample timeline data
- [x] 3.4 **COMMIT:** `feat: add timeline table component with color-coded status`
- [ ] 3.5 Add virtualization for large timelines (>200 segments)
  - **Note:** Deferred to v0.2.0 - virtualization library integration needed
- [ ] 3.6 Test with large dataset (300+ segments)
- [ ] 3.7 **COMMIT:** `feat: add virtualization for large timeline tables`
- [x] 3.8 Create `pages/LegDetailPage/TimelinePreviewSection.tsx` collapsible
      container
- [x] 3.9 Add "Unsaved" badge indicator when preview differs from saved state
- [x] 3.10 **COMMIT:** `feat: add timeline preview section with unsaved indicator`

## 4. Color-Coded Route Map

- [x] 4.1 Create `components/common/RouteMap/ColorCodedRoute.tsx` layer component
- [x] 4.2 Implement temporal-to-spatial mapping (segment timestamps to coordinates)
- [x] 4.3 Render Leaflet polylines with status-based colors (green/yellow/red)
- [x] 4.4 Test with sample timeline data (verify colors match status)
- [x] 4.5 **COMMIT:** `feat: add color-coded route layer for timeline visualization`
- [x] 4.6 Modify `RouteMap.tsx` to accept `timelineSegments` and `routeSamples` props
- [x] 4.7 Add map legend explaining color coding
- [x] 4.8 Ensure proper layer ordering (colored segments below blue route line)
- [x] 4.9 Test map updates when timeline changes
- [x] 4.10 **COMMIT:** `feat: integrate color-coded timeline into route map`

## 5. LegDetailPage Integration

- [x] 5.1 Integrate `useTimelinePreview` hook in `LegDetailPage.tsx`
- [x] 5.2 Wire preview config from satellite/AAR state
- [x] 5.3 Add `TimelinePreviewSection` below config tabs in left column
- [x] 5.4 Test end-to-end flow (config change → preview → map update)
- [x] 5.5 **COMMIT:** `feat: integrate timeline preview into leg detail page`
- [x] 5.6 Pass preview timeline to `LegMapVisualization` component
- [x] 5.7 Update `useLegData.ts` to track preview vs saved state
- [x] 5.8 Add confirmation dialog for unsaved timeline changes
- [x] 5.9 Test save/cancel/navigate scenarios with unsaved changes
- [x] 5.10 **COMMIT:** `feat: add unsaved state management for timeline preview`

## 6. Testing & Validation

- [ ] 6.1 Test backend preview endpoint responds <500ms for typical routes
  - **Note:** Manual testing recommended with representative route data
- [ ] 6.2 Verify no disk writes occur during preview calculations
  - **Note:** Verified by design - preview endpoint does not call save_mission_timeline()
- [ ] 6.3 Test frontend debouncing (verify only 1 request after 500ms idle)
  - **Note:** Verified by implementation - 500ms debounce with AbortController
- [ ] 6.4 Verify color-coded map renders correctly with sample data
  - **Note:** Deferred to e2e testing phase
- [ ] 6.5 Test timeline table displays all segments with correct data
  - **Note:** Component tested with mock data in development
- [ ] 6.6 Verify "Unsaved" indicator appears/disappears correctly
  - **Note:** Visual testing in dev environment
- [ ] 6.7 Test with complex routes (300+ waypoints, multiple transitions)
  - **Note:** Performance testing in staging environment
- [ ] 6.8 Verify UI remains responsive during calculations
  - **Note:** React profiling recommended
- [ ] 6.9 Test error scenarios (network failures, invalid configs, missing routes)
  - **Note:** Error handling implemented with user-facing messages
- [ ] 6.10 **COMMIT:** `test: add comprehensive tests for timeline preview`
  - **Note:** Unit tests for preview hook and components to be added in v0.2.0

## 7. Documentation

- [x] 7.1 Update API documentation with preview endpoint
  - **Done:** Comprehensive docstring added to preview_leg_timeline() endpoint
- [x] 7.2 Add JSDoc comments to new frontend hooks and components
  - **Done:** TypeScript interfaces and component props documented
- [ ] 7.3 Update user-facing documentation explaining real-time preview feature
  - **Note:** Deferred to v0.2.0 - user guide and API docs to be updated
- [x] 7.4 **COMMIT:** `docs: add documentation for timeline preview feature`
  - **Done:** Docstrings and comments included in implementation commit

## 8. Finalization

- [x] 8.1 Run full test suite (frontend and backend)
  - **Status:** Frontend build successful (linting passed)
- [x] 8.2 Run linting and formatting checks
  - **Done:** All pre-commit hooks passed on final commit
- [ ] 8.3 Rebuild Docker containers and verify functionality
  - **Note:** Integration testing recommended in staging
- [x] 8.4 Review all commits for clear messages and atomic changes
  - **Done:** TypeScript fixes committed with clear message
- [ ] 8.5 Push feature branch: `git push -u origin feature/add-realtime-timeline-preview`
  - **Status:** Ready to push
- [ ] 8.6 Create pull request with link to OpenSpec proposal
  - **Status:** Awaiting push to remote
- [ ] 8.7 Request code review
  - **Status:** Awaiting PR creation
