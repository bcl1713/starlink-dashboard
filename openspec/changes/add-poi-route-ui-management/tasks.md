# Implementation Tasks

## 1. Route Management Foundation

- [ ] 1.1 Extend `src/services/routes.ts` with CRUD methods (getRoute, deleteRoute, activateRoute, deactivateRoute, downloadRoute)
- [ ] 1.2 Create `src/hooks/api/useRoutes.ts` with React Query hooks (useRoutes, useRoute, useUploadRoute, useActivateRoute, useDeleteRoute, useDownloadRoute)
- [ ] 1.3 Create `src/types/route.ts` with TypeScript interfaces (RouteDetail, RoutePoint, TimingProfile)
- [ ] 1.4 Create `src/components/routes/RouteList.tsx` table component
- [ ] 1.5 Create `src/components/routes/RouteUploadDialog.tsx` with drag-drop support
- [ ] 1.6 Create `src/pages/RouteManagerPage.tsx` main page component
- [ ] 1.7 Test route upload and listing functionality

## 2. Route Details & Advanced Features

- [ ] 2.1 Create `src/components/routes/RouteDetailView.tsx` with map integration
- [ ] 2.2 Create `src/components/routes/RouteActionsMenu.tsx` for actions
- [ ] 2.3 Create `src/components/ui/ConfirmDialog.tsx` reusable confirmation dialog
- [ ] 2.4 Implement route activation/deactivation with visual feedback
- [ ] 2.5 Implement route deletion with cascade warning
- [ ] 2.6 Implement KML download functionality
- [ ] 2.7 Display timing profile and flight phase in route details
- [ ] 2.8 Test all route management operations

## 3. POI Management Foundation

- [ ] 3.1 Extend `src/services/pois.ts` with CRUD methods (createPOI, updatePOI, deletePOI, getPOI)
- [ ] 3.2 Create `src/hooks/api/usePOIs.ts` with React Query hooks (usePOIs, usePOI, useCreatePOI, useUpdatePOI, useDeletePOI)
- [ ] 3.3 Create `src/types/poi.ts` with TypeScript interfaces (POICreate, POIUpdate, POIWithETA)
- [ ] 3.4 Create `src/components/pois/POIList.tsx` table component
- [ ] 3.5 Create `src/components/pois/POIFilterBar.tsx` filter controls
- [ ] 3.6 Create `src/pages/POIManagerPage.tsx` shell with split-pane layout
- [ ] 3.7 Test POI listing and filtering

## 4. POI Creation & Map Interaction

- [ ] 4.1 Create `src/components/pois/POIMap.tsx` interactive map with click-to-place
- [ ] 4.2 Create `src/components/ui/IconPicker.tsx` icon selection dropdown
- [ ] 4.3 Create `src/components/pois/POIForm.tsx` with validation
- [ ] 4.4 Create `src/components/pois/POIDialog.tsx` modal wrapper
- [ ] 4.5 Wire up POI creation flow (form + map click)
- [ ] 4.6 Wire up POI editing flow
- [ ] 4.7 Implement POI deletion with confirmation
- [ ] 4.8 Test POI CRUD operations

## 5. Advanced POI Features & Real-Time Data

- [ ] 5.1 Extend `src/services/pois.ts` with `getPOIsWithETA()` method
- [ ] 5.2 Create `usePOIsWithETA()` React Query hook with polling
- [ ] 5.3 Display real-time ETA, bearing, and course status in POI list
- [ ] 5.4 Implement route projection visualization on map
- [ ] 5.5 Add route-aware status badges (ahead_on_route, already_passed, not_on_route)
- [ ] 5.6 Add POI filtering by category and course status
- [ ] 5.7 Implement "approaching" filter (within 30 min ETA)
- [ ] 5.8 Test real-time features with telemetry data

## 6. Navigation Integration & UI Polish

- [ ] 6.1 Update `src/App.tsx` with POI and Route navigation links
- [ ] 6.2 Update `src/App.tsx` with route definitions for `/pois` and `/routes`
- [ ] 6.3 Add comprehensive error handling (API errors, network failures, validation)
- [ ] 6.4 Implement loading states (skeleton loaders, spinners, progress bars)
- [ ] 6.5 Polish UI/UX (transitions, responsive layout, accessibility)
- [ ] 6.6 Add route/mission association dropdowns in POI form
- [ ] 6.7 Test navigation and page transitions
- [ ] 6.8 Test responsive layout on mobile/tablet

## 7. Deprecation & Documentation

- [ ] 7.1 Add deprecation banner to `/ui/pois` FastAPI template
- [ ] 7.2 Add deprecation banner to `/ui/routes` FastAPI template
- [ ] 7.3 Update API documentation marking FastAPI UI as deprecated
- [ ] 7.4 Test deprecation notices display correctly
- [ ] 7.5 Verify FastAPI UI endpoints remain functional

## 8. Testing & Validation

- [ ] 8.1 Manual testing: POI CRUD operations
- [ ] 8.2 Manual testing: Route upload/download/activation
- [ ] 8.3 Manual testing: Real-time ETA and course status
- [ ] 8.4 Manual testing: Map interactions and filtering
- [ ] 8.5 Manual testing: Navigation and integration
- [ ] 8.6 Verify all console errors resolved
- [ ] 8.7 Run frontend build validation (`npm run build`)
- [ ] 8.8 Verify backward compatibility with FastAPI UI
