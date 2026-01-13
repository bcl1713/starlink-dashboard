# Change: Add POI and Route Management UI to React Frontend

## Why

The FastAPI backend currently provides web UI pages at `/ui/pois` and `/ui/routes` for managing Points of Interest and Routes. These HTML-based interfaces are separate from the main React frontend application, creating a fragmented user experience and requiring users to switch between different UIs. Migrating these interfaces to the React frontend will provide a unified, modern user experience with better integration into the existing mission planning workflow.

## What Changes

- **NEW**: Add standalone POI Manager page (`/pois`) to React frontend
- **NEW**: Add standalone Route Manager page (`/routes`) to React frontend
- **NEW**: Implement full CRUD operations for POIs (create, read, update, delete)
- **NEW**: Implement route management operations (upload, activate, deactivate, delete, download)
- **NEW**: Interactive map with click-to-place POI functionality
- **NEW**: Real-time ETA calculations with dual-mode support (anticipated/estimated)
- **NEW**: Course status and bearing calculations for POIs
- **NEW**: Route projection visualization for POIs on active routes
- **NEW**: KML file upload/download functionality in React UI
- **NEW**: POI and Route filtering capabilities
- **MODIFIED**: Update main navigation to include POI and Route links
- **DEPRECATED**: Mark FastAPI UI templates (`/ui/pois`, `/ui/routes`) with deprecation notices

All features from the existing FastAPI UI will be replicated with full feature parity, including:
- POI management with route/mission association
- Route activation/deactivation with POI projection
- Real-time telemetry integration (ETA, bearing, course status)
- Timing profile display for routes
- Flight phase tracking
- Associated POIs display for routes

## Impact

### Affected Specs
- **NEW SPEC**: `poi-management` - POI CRUD operations and real-time features
- **NEW SPEC**: `route-management` - Route management and activation
- **RELATED**: `mission-metadata` - POI/Route integration with missions

### Affected Code

**Frontend (New Files - ~18 files):**
- `src/pages/POIManagerPage.tsx` - POI management page
- `src/pages/RouteManagerPage.tsx` - Route management page
- `src/components/pois/` - POI components (6 files)
- `src/components/routes/` - Route components (4 files)
- `src/components/ui/` - Shared components (2 files: IconPicker, ConfirmDialog)
- `src/hooks/api/usePOIs.ts` - POI React Query hooks
- `src/hooks/api/useRoutes.ts` - Route React Query hooks
- `src/types/poi.ts` - POI TypeScript interfaces
- `src/types/route.ts` - Route TypeScript interfaces

**Frontend (Modified Files - 3 files):**
- `src/App.tsx` - Add navigation links and routes
- `src/services/pois.ts` - Add CRUD methods
- `src/services/routes.ts` - Add management methods

**Backend (Modified Files - 1 file):**
- `backend/starlink-location/app/api/ui/templates.py` - Add deprecation banners

### User-Facing Changes
- POI and Route management accessible from main navigation
- Unified interface consistent with Missions and Satellites pages
- Improved user experience with React components and real-time updates
- FastAPI UI remains functional but shows deprecation notice

### Migration Path
- No breaking changes to API endpoints
- FastAPI UI templates remain functional during transition
- Users can switch to new React UI at their convenience
- Eventual removal of FastAPI UI templates in future release

## Dependencies
- Existing API endpoints (`/api/pois/*`, `/api/routes/*`)
- React Router v7 for navigation
- TanStack React Query for data fetching
- Leaflet + React-Leaflet for map visualization
- Existing `RouteMap` component for map rendering
