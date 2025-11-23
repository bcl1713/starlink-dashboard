# Context for mission-leg-planning-ui

**Branch:** `feat/mission-leg-planning-ui`
**Folder:** `dev/active/mission-leg-planning-ui/`
**Last Updated:** 2025-11-23

---

## Background

The current system treats each "mission" as an isolated entity, but real-world operations consist of multiple connected flight legs that form a complete mission. Users need to plan entire missions with multiple legs as cohesive units, configure satellite communications (X-Band, Ka, Ku) and air-refueling segments for each leg, and export/import complete mission packages for portability across systems. This work introduces the Mission > Mission Leg hierarchy, refactors backend models, implements comprehensive export/import, and builds a TypeScript React-based planning UI to streamline mission planning workflows.

**Why now:** Current workaround requires managing legs separately, leading to fragmented planning and difficulty sharing complete mission plans between systems. This refactor enables proper mission lifecycle management.

---

## Relevant Code Locations

**Backend - Models:**
- `backend/starlink-location/app/mission/models.py` — Current Mission model (will be renamed to MissionLeg)
- `backend/starlink-location/app/mission/models.py` — New Mission model (container) to be added

**Backend - Storage:**
- `backend/starlink-location/app/mission/storage.py` — Storage layer for missions (will support hierarchy)
- `data/missions/` — Current flat structure (will become hierarchical)

**Backend - API Routes:**
- `backend/starlink-location/app/mission/routes.py` — Current mission endpoints (will remain as v1, deprecated)
- `backend/starlink-location/app/mission/routes_v2.py` — New v2 endpoints (to be created)

**Backend - Export/Import:**
- `backend/starlink-location/app/mission/exporter.py` — Current timeline export (PDF, XLSX, etc.)
- `backend/starlink-location/app/mission/package_exporter.py` — New mission package exporter (to be created)
- `backend/starlink-location/app/mission/package_importer.py` — New mission package importer (to be created)

**Frontend (new):**
- `frontend/mission-planner/` — React + TypeScript application root (to be created)
- `frontend/mission-planner/src/components/` — UI components (ShadCN-based)
- `frontend/mission-planner/src/hooks/` — Custom React hooks
- `frontend/mission-planner/src/services/` — API client services
- `frontend/mission-planner/src/types/` — TypeScript type definitions
- `frontend/mission-planner/src/lib/` — Utility functions

**Docker:**
- `docker-compose.yml` — Will need frontend service added
- `frontend/mission-planner/Dockerfile` — Frontend build container (to be created)

---

## Dependencies

**Backend Libraries (existing):**
- FastAPI — Web framework
- Pydantic — Data validation and models
- pandas, openpyxl — Excel export
- reportlab — PDF generation
- python-pptx — PowerPoint export
- zipfile (stdlib) — For package export/import

**Frontend Libraries (to be added):**
- React 18 — UI framework
- TypeScript 5+ — Type safety
- Vite — Build tooling and dev server
- React Router — Navigation
- TanStack Query (React Query) — Server state management
- Zustand — Client state management
- ShadCN/UI — Component library (Radix UI primitives)
- Tailwind CSS — Utility-first styling (required for ShadCN)
- Leaflet + react-leaflet — Map visualization
- React Hook Form — Form management
- Zod — Schema validation (runtime + TypeScript types)
- Axios — HTTP client
- react-dropzone — File upload
- Vitest — Unit testing framework
- React Testing Library — Component testing
- Playwright — E2E testing
- Prettier — Code formatting
- ESLint + TypeScript ESLint — Linting

**Environment Variables:**
- `CORS_ORIGINS` — Add frontend dev server URL for CORS
- `FRONTEND_DEV_MODE` — Flag for serving frontend separately in dev

**Services:**
- Backend FastAPI server — Port 8000
- Frontend dev server (Vite) — Port 5173 (Vite default, development)
- Grafana — Port 3000 (existing, no conflicts)

---

## Constraints & Assumptions

**Constraints:**
- **350-line hard cap per file** — Enforces separation of concerns, no exceptions
- **SOLID principles required** — All React components/hooks must follow SOLID design
- **TypeScript strict mode** — No `any` types without explicit justification
- Export packages must include pre-generated documents (PDF, XLSX, PPTX, CSV) for each leg
- Import must handle version mismatches gracefully (log warnings, don't fail)
- File size limit: Mission export packages should remain under 100MB for reasonable transfer
- Docker environment: All development must work within Docker Compose setup

**SOLID Principles Enforcement:**
- **Single Responsibility**: Each component/hook/service does one thing
  - Example: `MissionCard` displays, `useMissions` fetches data, `MissionForm` handles input
- **Open/Closed**: Components extensible via props/composition, not modification
  - Example: `Button` accepts variants, not hardcoded styles
- **Liskov Substitution**: Component variants are interchangeable
  - Example: All form field components accept same base props interface
- **Interface Segregation**: Props interfaces minimal and focused
  - Example: `MissionCardProps` only includes display data, not API concerns
- **Dependency Inversion**: Depend on abstractions (hooks, contexts) not implementations
  - Example: Components use `useMissions()` hook, not direct API calls

**Assumptions:**
- Users have basic familiarity with flight planning and KML files
- Export/import will primarily be between same-version instances (cross-version is best-effort)
- X-Band satellite assignments are manual (user-provided)
- Ka transitions remain auto-calculated based on coverage (CommKa.kmz)
- Ku/Starlink is assumed available unless user specifies outages

---

## Risks

**Risk 1: Model refactoring breaks existing functionality**
- **Impact:** Grafana dashboards, existing API clients, or tests could fail
- **Mitigation:** Maintain v1 API endpoints, comprehensive testing before merge, phased rollout

**Risk 2: Export/import compatibility issues**
- **Impact:** Mission packages may fail to import on different systems
- **Mitigation:** Strict validation, manifest with version metadata, checksums for integrity

**Risk 3: Frontend performance with large missions (10+ legs)**
- **Impact:** UI could lag when rendering many legs with routes/POIs
- **Mitigation:** Virtualized lists, lazy loading, pagination, map clustering

**Risk 4: File size limit creates too many small files**
- **Impact:** 350-line cap might create excessive file fragmentation
- **Mitigation:** Thoughtful component boundaries, co-locate related code in feature folders

**Risk 5: SOLID principles increase initial development time**
- **Impact:** More upfront architecture work vs. quick prototyping
- **Mitigation:** Patterns established early become templates; long-term maintainability gains

---

## Testing Strategy

### Backend Testing

**Unit Tests:**
- Test MissionLeg model rename (all fields, serialization)
- Test new Mission model (validation, nested legs)
- Test storage hierarchy (create, read, update, delete)
- Test export package generation (zip structure, manifests, checksums)
- Test import validation (schema checks, error handling)

**Integration Tests:**
- Test v2 API endpoints (CRUD operations)
- Test export endpoint (download zip, verify contents)
- Test import endpoint (upload zip, verify reconstruction)
- Test roundtrip (export → import → verify equality)

### Frontend Testing

**Unit Tests (Vitest):**
- Test utility functions (date formatting, validation helpers)
- Test custom hooks in isolation (mock API responses)
- Test Zod schemas and type guards

**Component Tests (React Testing Library):**
- Test MissionList renders missions correctly
- Test MissionEditor wizard flow (multi-step navigation)
- Test LegEditor form validation
- Test SatelliteTransitionEditor data binding
- Test export/import dialogs
- Each component test file < 350 lines

**E2E Tests (Playwright):**
1. Navigate to http://localhost:5173/missions
2. Click "Create New Mission"
3. Fill in mission details (name, description)
4. Add 2 legs with routes
5. Configure X-Band transitions for each leg
6. Add AAR segment to leg 1
7. Save mission
8. Export mission as zip
9. Delete mission
10. Import zip file
11. Verify mission recreated with all legs, routes, POIs

### Manual Verification

- Create mission with 3 legs
- Upload KML routes for each leg
- Configure satellite transitions (X-Band, Ka outages, Ku outages)
- Define AAR segments using waypoint names
- Export mission package
- Inspect zip contents manually (verify all files present)
- Import package on separate Docker instance
- Confirm all data matches original

---

## Code Quality Standards

**File Organization:**
```
frontend/mission-planner/src/
├── components/
│   ├── missions/          # Mission-related components
│   ├── legs/              # Leg-related components
│   ├── satellites/        # Satellite config components
│   ├── ui/                # ShadCN UI components
│   └── common/            # Shared presentational components
├── hooks/
│   ├── api/               # API-related hooks (useMissions, useLegs, etc.)
│   ├── ui/                # UI state hooks (useDialog, useToast, etc.)
│   └── utils/             # Utility hooks
├── services/
│   ├── api-client.ts      # Axios instance configuration
│   ├── missions.ts        # Mission API calls
│   ├── legs.ts            # Leg API calls
│   └── export-import.ts   # Export/import API calls
├── types/
│   ├── mission.ts         # Mission type definitions
│   ├── leg.ts             # Leg type definitions
│   └── api.ts             # API response types
├── lib/
│   ├── utils.ts           # Utility functions
│   └── validation.ts      # Zod schemas
└── App.tsx                # Root component
```

**Linting & Formatting:**
- Prettier enforces consistent formatting
- ESLint catches common errors and enforces best practices
- TypeScript strict mode catches type errors
- Pre-commit hooks run linting/formatting automatically

**Line Limit Enforcement:**
- ESLint rule: `max-lines: ["error", 350]`
- CI/CD pipeline fails if any file exceeds 350 lines
- No exceptions (use composition, extraction, or refactoring)

---

## References

- **Backend Models:** `backend/starlink-location/app/mission/models.py`
- **Current Mission API:** `backend/starlink-location/app/mission/routes.py`
- **Current Export System:** `backend/starlink-location/app/mission/exporter.py`
- **CLAUDE.md:** Root-level project documentation
- **Design Document:** `docs/design-document.md`
- **ShadCN/UI Docs:** https://ui.shadcn.com/
- **React Query Docs:** https://tanstack.com/query/latest
- **Zustand Docs:** https://docs.pmnd.rs/zustand/
