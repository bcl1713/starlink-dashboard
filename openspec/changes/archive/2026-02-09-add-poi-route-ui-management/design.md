## Context

The Starlink dashboard currently has a dual-UI situation: the main React frontend (Vite + React 19 + TypeScript) handles missions, satellites, and data export, while POI and Route management lives in separate FastAPI-rendered HTML templates at `/ui/pois` and `/ui/routes`. This forces users to context-switch between two different UIs with different interaction patterns.

The React frontend already has established patterns for feature development: Axios-based service layers, TanStack React Query hooks with automatic cache invalidation, shadcn/ui components (Tailwind + Radix UI), and Leaflet-based map visualization. The backend API endpoints (`/api/pois/*`, `/api/routes/*`) are already built and well-structured — this change is purely frontend.

A significant portion of the implementation is already complete. The POI and Route pages, components, services, hooks, and types have been built (tasks 1-4, plus UX improvements in 5b/5c). What remains is the advanced real-time POI features (ETA, projections, course status), navigation polish, deprecation banners, and testing.

## Goals / Non-Goals

**Goals:**
- Full feature parity with the existing FastAPI UI for both POI and Route management
- Consistent UX with the existing React pages (Missions, Satellites, Export)
- Real-time telemetry integration (ETA, bearing, course status) via polling
- Interactive map-first workflow with click-to-place POI creation
- Clean integration into the existing navigation and routing structure

**Non-Goals:**
- Removing the FastAPI UI endpoints (they get deprecation banners only)
- Adding new backend API endpoints — all needed endpoints already exist
- Real-time WebSocket connections — polling via React Query is sufficient and matches existing patterns
- Mobile-native experience — responsive layout adapts but desktop is primary
- Automated testing (unit/integration) — manual testing is the validation approach for this change

## Decisions

### 1. Split-pane layout with map prominence

**Decision**: POI Manager uses a 60/40 split (map left, list/controls right). Route Manager uses a list + detail dialog pattern.

**Rationale**: POIs are inherently spatial — users need to see where things are relative to the route. The map-first layout matches how operators think about POIs. Routes are more tabular (upload, activate, delete) so a list view with detail dialogs fits better.

**Alternatives considered**:
- Full-page map with floating panels — too complex, obscures data tables
- Unified POI+Route page — the two concerns are distinct enough to warrant separate pages

### 2. React Query polling for real-time ETA data

**Decision**: Use `usePOIsWithETA()` hook with 5-second polling interval via React Query's `refetchInterval`.

**Rationale**: Matches the existing pattern used elsewhere in the app. The `/api/pois/telemetry/with_eta` endpoint returns pre-computed ETA, bearing, and course status. Polling at 5s is sufficient for flight tracking and avoids WebSocket complexity.

**Alternatives considered**:
- WebSocket/SSE for push updates — unnecessary complexity, polling is adequate for this refresh rate
- Shorter polling interval — 5s balances freshness with server load

### 3. Existing service + hook layer (already built)

**Decision**: Extend `poisService` and `routesApi` objects in existing service files. React Query hooks follow the established `use{Feature}` pattern with automatic cache invalidation on mutations.

**Rationale**: This is a continuation of the pattern already in place for missions and satellites. Services use the shared Axios client (`api-client.ts`) with centralized error handling.

### 4. shadcn/ui component library with Tailwind

**Decision**: Use existing UI primitives (`Button`, `Card`, `Dialog`, `Table`, `Select`, etc.) from `components/ui/`. New shared components (`ConfirmDialog`, `IconPicker`) added to `components/ui/`.

**Rationale**: Consistent with the design system already established. No new dependencies needed — Radix UI primitives, lucide-react icons, and Tailwind classes cover all requirements.

### 5. Cross-cache invalidation on route activation

**Decision**: When a route is activated/deactivated, invalidate both `['routes']` and `['pois']` query keys.

**Rationale**: Route activation changes which POIs are "active" and triggers projection recalculation. POI ETA data depends on the active route. Both caches must be fresh after activation changes.

### 6. Leaflet for all map rendering

**Decision**: POIMap uses Leaflet directly (react-leaflet). Route detail views reuse the existing `RouteMap` component from `components/common/RouteMap/`.

**Rationale**: RouteMap already handles IDL crossing, coordinate segmentation, and transition overlays. POIMap needs simpler functionality (markers, click handler, route line) so a lightweight component is appropriate.

### 7. Deprecation banners on FastAPI UI

**Decision**: Add HTML deprecation banners to the Jinja2 templates at `/ui/pois` and `/ui/routes` pointing users to the new React UI pages.

**Rationale**: Non-breaking change. Users who have bookmarked the old URLs see a clear migration path. Templates remain functional until a future removal.

## Risks / Trade-offs

**ETA polling creates server load** → 5-second interval is a reasonable balance. The backend already caches ETA calculations. Polling only runs when the POI Manager page is active (React Query pauses on tab blur).

**Route projection accuracy depends on backend computation** → The frontend displays pre-computed projection data from the API. If the backend projection algorithm changes, the frontend automatically picks up the new values. No frontend-side geometric computation needed.

**Two map implementations (POIMap vs RouteMap)** → POIMap is intentionally simpler than RouteMap. RouteMap handles transitions, timeline overlays, and satellite outage visualization that POIs don't need. Keeping them separate avoids bloating either component.

**Large POI/route datasets could slow the UI** → The table renders all rows without virtualization. For the expected data volumes (tens to low hundreds of POIs/routes) this is fine. If scale becomes an issue, virtualized tables can be added later.

**FastAPI UI deprecation without removal** → Users might continue using the old UI. The deprecation banner makes the migration path clear, and eventual removal is tracked as a future change.
