# Project Context

## Purpose

The **Starlink Dashboard** is a Docker-based monitoring and mission planning
system for mobile Starlink terminals. It provides:

- **Real-time monitoring** of Starlink terminal metrics (latency, throughput,
  obstructions, GPS position)
- **Mission planning** with interactive route visualization on maps
- **ETA calculation** with Points of Interest (POI) tracking
- **Dual-mode operation**: Live mode (physical Starlink hardware) and
  Simulation mode (offline development)
- **Historical metrics** storage and visualization via Prometheus and Grafana
- **Mission export** capabilities (KML, GeoJSON, PowerPoint, PDF, Excel)

**Primary Use Case:** Maritime, aviation, or mobile vehicle operations
requiring Starlink connectivity monitoring and route planning with satellite
coverage awareness.

**Version:** 0.3.0 (Phase 0 Complete - Foundation + ETA Route Timing Feature)

## Tech Stack

### Frontend: Mission Planner Web Application

- **Framework:** React 19.2.0 (latest features)
- **Language:** TypeScript 5.9.3 (strict mode)
- **Build Tool:** Vite 7.2.4 (lightning-fast dev server)
- **UI Framework:** TailwindCSS 4.1.17 (utility-first styling)
- **Component Library:** Radix UI (headless, accessible components)
- **State Management:** Zustand 5.0.8 (lightweight state)
- **Forms:** React Hook Form 7.66.1 + Zod 4.1.12 (validation)
- **Data Fetching:** TanStack React Query 5.90.10 (server state)
- **Maps:** Leaflet 1.9.4 + React Leaflet 5.0.0 (interactive maps)
- **HTTP Client:** Axios 1.13.2
- **Testing:** Playwright 1.56.1 (E2E), Vitest 4.0.13 (unit)
- **Icons:** Lucide React
- **Runtime:** Node.js >= 22.0.0

### Backend: Starlink Location Service

- **Framework:** FastAPI 0.104.0+ (async Python web framework)
- **Language:** Python 3.11 (async/await support)
- **Server:** Uvicorn [standard] 0.24.0+ (ASGI server)
- **Validation:** Pydantic 2.0+ (data models and settings)
- **Geospatial:** FastKML 1.3+, GeoJSON 2.5+, Cartopy 0.22+
- **Data Processing:** NumPy 1.24+, Pandas 2.0+
- **Document Generation:** Python-PPTX 0.6.21, ReportLab 4.0+, OpenPyXL 3.1+
- **Starlink Integration:** starlink-grpc-core 1.2+, gRPCio 1.50+
  (communicates with physical Starlink dish at 192.168.100.1:9200)
- **Metrics:** Prometheus-client 0.19+ (metrics export)
- **Rate Limiting:** SlowAPI 0.1.9+
- **Testing:** Pytest 7.4+, Pytest-AsyncIO 0.21+, Pytest-Cov 4.1+

### Infrastructure & Monitoring

- **Containerization:** Docker + Docker Compose (multi-container orchestration)
- **Metrics Storage:** Prometheus 2.x (time-series database)
- **Visualization:** Grafana 10.x (dashboards and alerting)
- **Web Server:** Nginx (production frontend serving)
- **Data Storage:** File-based (KML, GeoJSON, YAML, JSON - no traditional
  database)

### Code Quality & Development Tools

- **Python Formatting:** Black (88 char line length)
- **Python Linting:** Ruff (fast linter with auto-fix)
- **Python Type Checking:** MyPy (static type analysis)
- **TypeScript Linting:** ESLint 9.39.1 + TypeScript ESLint
- **JS/TS Formatting:** Prettier 3.6.2 (80 char print width)
- **Markdown Linting:** Markdownlint-cli2
- **Pre-commit Hooks:** Git hooks for automated quality checks
- **Version Control:** Git (main branch workflow)

## Project Conventions

### Code Style

**Python (Backend):**

- **Formatter:** Black with 88 character line length (PEP 8 compliant)
- **Linter:** Ruff for syntax, security, and style checks
- **Type Hints:** Required for all function parameters and return types
- **Docstrings:** PEP 257 format for all public functions and classes
- **File Size:** Prefer files under 300 lines; split into modules if larger
- **Naming:**
  - `snake_case` for variables, functions, modules
  - `PascalCase` for classes
  - `UPPER_SNAKE_CASE` for constants
- **Comments:** Explain "why" not "what"; clarify intent and reasoning
- **Async:** Use `async/await` for I/O operations in FastAPI routes

**TypeScript/JavaScript (Frontend):**

- **Formatter:** Prettier with 80 character print width
- **Linter:** ESLint with TypeScript support
- **Type Safety:** TypeScript strict mode enabled; minimize `any` types
- **File Size:** Prefer files under 300 lines; extract sub-components
- **Naming:**
  - `camelCase` for variables and functions
  - `PascalCase` for React components and TypeScript types/interfaces
  - `UPPER_SNAKE_CASE` for constants
- **Components:** Functional components with hooks (no class components)
- **Props:** Define explicit TypeScript interfaces for component props
- **JSDoc:** Add JSDoc comments to exported functions

**Markdown (Documentation):**

- **Formatter:** Prettier with 80 character line width and prose wrap
- **Linter:** Markdownlint-cli2
- **File Size:** Prefer files under 300 lines; split into sub-documents
- **Naming:** `lowercase-with-hyphens.md` format
- **Links:** Use relative paths only (e.g., `../api/README.md`)
- **Code Blocks:** Include language identifier (```python,```bash, ```typescript)
- **Headings:** Consistent hierarchy (no H1 jump to H3)
- **Purpose Statement:** For docs >100 lines, include brief purpose and audience

### Architecture Patterns

**Backend (FastAPI):**

- **Layered Architecture:**
  - `app/api/` - Route handlers (HTTP endpoints)
  - `app/services/` - Business logic (POI Manager, Route Manager)
  - `app/core/` - Core services (config, logging, metrics, ETA)
  - `app/models/` - Pydantic data models
- **Dependency Injection:** Use FastAPI's dependency injection for shared resources
- **Configuration:** Environment-based config via Pydantic Settings (`.env` file)
- **Error Handling:** Custom exception handlers with proper HTTP status codes
- **API Versioning:** `/api/v2/` prefix for all endpoints
- **Health Checks:** `/health` endpoint for container orchestration

**Frontend (React + Vite):**

- **Component-Based Architecture:**
  - `src/pages/` - Top-level page components
  - `src/components/` - Reusable UI components
  - `src/services/` - API client services (Axios)
  - `src/types/` - TypeScript type definitions
  - `src/utils/` - Utility functions
- **State Management:** Zustand stores for global state
- **Server State:** TanStack React Query for API data caching
- **Form Management:** React Hook Form + Zod for validation
- **Component Variants:** class-variance-authority for component styling variants
- **CSS Strategy:** TailwindCSS utility classes (avoid custom CSS files)

**Data Storage:**

- **File-Based Persistence:** No traditional database
  - Routes: KML/GeoJSON files in `/data/routes`
  - Missions: JSON metadata in `/data/missions`
  - Config: YAML files
  - Metrics: Prometheus time-series database

**Docker & Deployment:**

- **Multi-Stage Builds:** Separate builder and runtime stages for optimized images
- **Non-Root Execution:** Containers run as non-root user for security
- **Health Checks:** Built into docker-compose.yml
- **Environment Variables:** `.env` file for configuration (never commit
  sensitive data)

### Testing Strategy

**Backend (Python):**

- **Framework:** Pytest with async support
- **Test Types:**
  - Unit tests in `tests/unit/`
  - Integration tests in `tests/integration/`
  - Performance tests in `tests/performance/`
- **Coverage:** Pytest-Cov for coverage reports
- **Type Checking:** MyPy static analysis (run before commits)
- **Smoke Tests:** Quick validation after Docker rebuild

**Frontend (TypeScript):**

- **Unit Testing:** Vitest with Testing Library
- **E2E Testing:** Playwright for end-to-end workflows
- **Type Checking:** TypeScript compiler (`tsc --noEmit`)
- **Build Validation:** Run `npm run build` before commits
- **Linting:** ESLint validation

**Documentation:**

- **Link Validation:** Manual validation with `rg` or markdown-link-check
- **Formatting:** Markdownlint-cli2 checks

**Pre-Deployment Checks:**

- Backend: Docker rebuild required for Python changes

  ```bash
  docker compose down && docker compose build --no-cache && docker compose up -d
  curl http://localhost:8000/health
  ```

- Frontend: Build validation

  ```bash
  cd frontend/mission-planner && npm run build
  ```

### Git Workflow

**Branch Strategy:**

- **Main Branch:** `main` (stable, deployable code)
- **Feature Branches:** `feature/your-feature-name` (branch from main)
- **Spec Branches:** `specs/NNN-spec-name` (for OpenSpec proposals)

**Commit Conventions:**

- **Format:** `type: description` (lowercase, imperative mood)
- **Types:**
  - `feat:` - New feature
  - `fix:` - Bug fix
  - `docs:` - Documentation only
  - `refactor:` - Code restructuring (no functionality change)
  - `test:` - Adding or updating tests
  - `chore:` - Maintenance tasks
- **Examples:**
  - `feat: add KML route import endpoint`
  - `fix: resolve ETA calculation timezone issue`
  - `docs: update API reference for POI endpoints`

**Pull Request Process:**

1. Ensure tests pass and code quality checks succeed
2. Update documentation if adding/changing features
3. Write clear PR description with rationale
4. Reference related issues (`fixes #123`, `closes #456`)
5. Wait for review and address feedback

**Pre-Commit Hooks:**

- Automated via `.pre-commit-config.yaml`
- Runs Black, Ruff, Prettier, ESLint, Markdownlint
- Must pass before commit succeeds

**Important Notes:**

- Backend Python changes require full Docker rebuild to take effect
- Never use `grep` - always use `rg` (ripgrep) instead
- Do not credit yourself on commits and PRs (team-based contribution)

## Domain Context

### Starlink Terminal Integration

- **Communication:** gRPC protocol to Starlink dish at `192.168.100.1:9200`
- **Metrics Collected:**
  - GPS position (latitude, longitude, altitude)
  - Network stats (latency, throughput, packet loss)
  - Obstructions (satellite visibility)
  - Terminal state (online/offline, boot status)
- **Operating Modes:**
  - **Live Mode:** Connects to physical Starlink hardware via gRPC
  - **Simulation Mode:** Offline development with simulated GPS/metrics data

### Geospatial Concepts

- **Routes:** Geographic paths defined as KML or GeoJSON LineStrings
- **POIs (Points of Interest):** Named waypoints along routes with descriptions
- **ETA (Estimated Time of Arrival):** Calculated based on current GPS
  position, speed, and route geometry
- **Coverage Areas:** Satellite coverage zones (future feature)
- **Map Projections:** Cartopy for advanced map projections (Mercator,
  Lambert, etc.)

### Mission Planning

- **Mission:** Collection of route legs with metadata (name, description, timeline)
- **Leg:** Individual route segment with start/end points and POIs
- **Export Formats:** KML, GeoJSON, PowerPoint (briefing slides), PDF
  (reports), Excel (waypoint tables)
- **Import:** KML/KMZ file upload with automatic route and POI extraction

### Metrics & Monitoring

- **Prometheus Metrics:** Gauges and counters for Starlink stats, API
  performance, system health
- **Grafana Dashboards:** Real-time visualization of metrics with custom dashboards
- **Retention:** Prometheus data retention configurable via environment variables
- **Alerting:** Grafana alerts for connection loss, high latency, obstructions

## Important Constraints

### Technical Constraints

- **Python Version:** Requires Python 3.11+ (for async/await and type hints)
- **Node Version:** Requires Node.js >= 22.0.0 (for frontend build)
- **Docker:** Required for deployment and backend development
- **Network:** Backend must access Starlink dish at `192.168.100.1:9200` in
  Live Mode
- **File Size Limits:** Prefer files under 300 lines for maintainability
- **Breaking Changes:** Avoid breaking API changes without discussion and
  versioning

### Development Constraints

- **Docker Rebuild:** Backend Python changes require full container rebuild
  (not hot-reload)
- **Environment Variables:** Configuration via `.env` file (never commit secrets)
- **Pre-commit Hooks:** Must pass before commits succeed
- **Type Safety:** All code must have proper type annotations
- **Documentation:** All new features require documentation updates

### Data Constraints

- **No Traditional Database:** File-based persistence only (KML, JSON, YAML)
- **Concurrency:** FileLocker used for concurrent file access
- **Route Storage:** Routes stored in `/data/routes` and
  `/data/sim_routes`
- **Mission Storage:** Missions stored in `/data/missions`

### Security Constraints

- **Non-Root Containers:** All Docker containers run as non-root users
- **No Secrets in Repo:** Never commit API keys, credentials, or `.env` files
- **CORS:** Configured for development (localhost only by default)
- **Rate Limiting:** SlowAPI enforces rate limits on API endpoints

## External Dependencies

### Starlink Hardware (Live Mode)

- **Service:** Starlink Dish gRPC API
- **Address:** `192.168.100.1:9200` (default Starlink dish IP and gRPC
  port)
- **Protocol:** gRPC (via starlink-grpc-core library)
- **Data:** Real-time GPS, network metrics, obstruction data
- **Fallback:** Simulation mode available when hardware unavailable

### Monitoring Stack

- **Prometheus:** Metrics collection and storage (port 9090)
- **Grafana:** Dashboard visualization (port 3000, default credentials:
  admin/admin)
- **Integration:** Backend exposes `/metrics` endpoint in Prometheus format

### Third-Party Libraries

- **Frontend:**
  - Leaflet (map rendering)
  - Radix UI (accessible components)
  - TailwindCSS (styling framework)
  - TanStack React Query (data fetching)
- **Backend:**
  - FastKML (KML parsing and generation)
  - Cartopy (map projections)
  - Matplotlib (plotting for exports)
  - ReportLab (PDF generation)

### Development Services

- **Docker Hub:** Base images (python:3.11-slim, node:22-alpine, nginx:alpine)
- **npm Registry:** Frontend package dependencies
- **PyPI:** Python package dependencies

### Documentation

- **Grafana Docs:** <https://grafana.com/docs/>
- **Prometheus Docs:** <https://prometheus.io/docs/>
- **FastAPI Docs:** <https://fastapi.tiangolo.com/>
- **Docker Docs:** <https://docs.docker.com/>
