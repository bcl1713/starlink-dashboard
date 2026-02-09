# Implementation Tasks

## 1. Route Management Foundation

- [x] 1.1 Extend `src/services/routes.ts` with CRUD methods (getRoute, deleteRoute, activateRoute, deactivateRoute, downloadRoute)
- [x] 1.2 Create `src/hooks/api/useRoutes.ts` with React Query hooks (useRoutes, useRoute, useUploadRoute, useActivateRoute, useDeleteRoute, useDownloadRoute)
- [x] 1.3 Create `src/types/route.ts` with TypeScript interfaces (RouteDetail, RoutePoint, TimingProfile)
- [x] 1.4 Create `src/components/routes/RouteList.tsx` table component
- [x] 1.5 Create `src/components/routes/RouteUploadDialog.tsx` with drag-drop support
- [x] 1.6 Create `src/pages/RouteManagerPage.tsx` main page component
- [x] 1.7 Test route upload and listing functionality

## 2. Route Details & Advanced Features

- [x] 2.1 Create `src/components/routes/RouteDetailView.tsx` with map integration
- [x] 2.2 Create `src/components/routes/RouteActionsMenu.tsx` for actions
- [x] 2.3 Create `src/components/ui/ConfirmDialog.tsx` reusable confirmation dialog
- [x] 2.4 Implement route activation/deactivation with visual feedback
- [x] 2.5 Implement route deletion with cascade warning
- [x] 2.6 Implement KML download functionality
- [x] 2.7 Display timing profile and flight phase in route details
- [x] 2.8 Test all route management operations

## 3. POI Management Foundation

- [x] 3.1 Extend `src/services/pois.ts` with CRUD methods (createPOI, updatePOI, deletePOI, getPOI)
- [x] 3.2 Create `src/hooks/api/usePOIs.ts` with React Query hooks (usePOIs, usePOI, useCreatePOI, useUpdatePOI, useDeletePOI)
- [x] 3.3 Create `src/types/poi.ts` with TypeScript interfaces (POICreate, POIUpdate, POIWithETA)
- [x] 3.4 Create `src/components/pois/POIList.tsx` table component
- [x] 3.5 Create `src/components/pois/POIFilterBar.tsx` filter controls
- [x] 3.6 Create `src/pages/POIManagerPage.tsx` shell with split-pane layout
- [x] 3.7 Test POI listing and filtering

## 4. POI Creation & Map Interaction

- [x] 4.1 Create `src/components/pois/POIMap.tsx` interactive map with click-to-place
- [x] 4.2 Create `src/components/ui/IconPicker.tsx` icon selection dropdown
- [x] 4.3 Create `src/components/pois/POIForm.tsx` with validation
- [x] 4.4 Create `src/components/pois/POIDialog.tsx` modal wrapper
- [x] 4.5 Wire up POI creation flow (form + map click)
- [x] 4.6 Wire up POI editing flow
- [x] 4.7 Implement POI deletion with confirmation
- [x] 4.8 Test POI CRUD operations

## 5. Advanced POI Features & Real-Time Data

- [x] 5.1 Extend `src/services/pois.ts` with `getPOIsWithETA()` method
- [x] 5.2 Create `usePOIsWithETA()` React Query hook with polling
- [x] 5.3 Display real-time ETA, bearing, and course status in POI list
- [x] 5.4 Implement route projection visualization on map
- [x] 5.5 Add route-aware status badges (ahead_on_route, already_passed, not_on_route)
- [x] 5.6 Add POI filtering by category and course status
- [x] 5.7 ~~Implement "approaching" filter (within 30 min ETA)~~ REMOVED - unnecessary feature
- [x] 5.8 Test real-time features with telemetry data

## 5b. POI UX Improvements (User Feedback)

- [x] 5b.1 Fix "Show All POIs/Showing Active Only" button - removed confusing button, now showing all POIs by default
- [x] 5b.2 Add sortable columns to POI table - all columns now sortable with visual indicators
- [x] 5b.3 Add Route POIs toggle - hidden by default, visible with toggle button
- [x] 5b.4 Remove Approaching (30 mins) button - removed from filter bar
- [x] 5b.5 Make View/Edit buttons show POI on map - map now focuses on selected POI
- [x] 5b.6 Add click-to-position on map in edit view - POIDialog now includes a map for positioning
- [x] 5b.7 Fix dialog z-index issue on smaller screens - dialog was appearing behind map, increased z-index to 1000+
- [x] 5b.8 Fix CSP errors for Leaflet marker icons - switched from CDN to local bundled icons

## 5c. Route UX Improvements (User Feedback)

- [x] 5c.1 Add sortable columns to Route table - all columns now sortable with visual indicators
- [x] 5c.2 Create RouteDetailDialog - shows route details with map preview when clicking View
- [x] 5c.3 Wire up View button - clicking View now opens dialog with route map
- [x] 5c.4 Fix Route interface to match backend API - changed from active/created_at to is_active/imported_at
- [x] 5c.5 Fix waypoints display - now uses waypoints array length from detail endpoint (column renamed to "Points" for list, "Waypoints" shown in detail)

## 6. Navigation Integration & UI Polish

- [x] 6.1 Update `src/App.tsx` with POI and Route navigation links
- [x] 6.2 Update `src/App.tsx` with route definitions for `/pois` and `/routes`
- [x] 6.3 Add comprehensive error handling (API errors, network failures, validation)
- [x] 6.4 Implement loading states (skeleton loaders, spinners, progress bars)
- [x] 6.5 Polish UI/UX (transitions, responsive layout, accessibility)
- [x] 6.6 Add route/mission association dropdowns in POI form
- [x] 6.7 Test navigation and page transitions
- [x] 6.8 Test responsive layout on mobile/tablet

## 7. Deprecation & Documentation

- [x] 7.1 Add deprecation banner to `/ui/pois` FastAPI template
- [x] 7.2 Add deprecation banner to `/ui/routes` FastAPI template
- [x] 7.3 Update API documentation marking FastAPI UI as deprecated
- [x] 7.4 Test deprecation notices display correctly
- [x] 7.5 Verify FastAPI UI endpoints remain functional

## 8. Testing & Validation

- [x] 8.1 Manual testing: POI CRUD operations
- [x] 8.2 Manual testing: Route upload/download/activation
- [x] 8.3 Manual testing: Real-time ETA and course status
- [x] 8.4 Manual testing: Map interactions and filtering
- [x] 8.5 Manual testing: Navigation and integration
- [x] 8.6 Verify all console errors resolved
- [x] 8.7 Run frontend build validation (`npm run build`)
- [x] 8.8 Verify backward compatibility with FastAPI UI
