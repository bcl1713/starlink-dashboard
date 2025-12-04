# PRD: Project Scaffolding (Phase 1)

## 1. Introduction/Overview

This PRD covers Phase 1 of the Starlink Dashboard project: establishing the
foundational infrastructure for a Docker-based Starlink terminal monitoring
system. The goal is to create a complete project scaffold with all necessary
directories, Docker configurations, stub services, and development tooling that
will support subsequent development phases.

**Problem Statement:** Before implementing any monitoring functionality, we need
a consistent, reproducible development environment with all service containers,
networking, and persistent storage properly configured.

**Goal:** Create a working Docker Compose stack where all services start
successfully, communicate over a shared network, and can be accessed via their
respective web interfaces.

---

## 2. Goals

1. Establish a complete monorepo directory structure for all project components
2. Create a functional Docker Compose configuration with all three core services
3. Implement stub services that validate infrastructure without full
   functionality
4. Configure shared networking and persistent storage volumes
5. Provide environment-based configuration via `.env` files
6. Enable automated validation of the infrastructure setup
7. Initialize version control and basic project documentation

---

## 3. User Stories

**As a developer**, I want to clone the repository and run `docker compose up`
so that I can immediately have a working development environment without manual
configuration.

**As a developer**, I want all services to communicate over a shared Docker
network so that Prometheus can scrape metrics and Grafana can query Prometheus.

**As a developer**, I want persistent volumes for all data so that my metrics
and dashboards survive container restarts.

**As a developer**, I want a smoke test script so that I can validate my
environment is correctly configured before starting development work.

**As a project maintainer**, I want clear documentation and example
configuration files so that new contributors can onboard quickly.

---

## 4. Functional Requirements

### 4.1 Directory Structure

1. The system must create the following directory structure:

```text
starlink-dashboard/
├── .github/
│   └── workflows/          # Placeholder for future CI/CD
├── backend/
│   └── starlink-location/
│       ├── app.py          # Stub FastAPI application
│       ├── Dockerfile
│       └── requirements.txt
├── data/
│   ├── routes/             # For KML route files
│   └── sim_routes/         # For simulation route files
├── docs/                   # (already exists)
│   ├── design-document.md
│   └── phased-development-plan.md
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── provisioning/   # For future dashboard configs
├── tasks/                  # For PRDs and task tracking
├── .env                    # Environment variables (gitignored)
├── .env.example            # Example environment configuration
├── .gitignore
├── CLAUDE.md               # (already exists)
├── docker-compose.yml
├── README.md
└── test-phase1.sh          # Smoke test script
```

### 4.2 Docker Compose Configuration

1. The system must define a `docker-compose.yml` with three services:
   - `starlink-location` (custom Python service)
   - `prometheus` (official Prometheus image, latest)
   - `grafana` (official Grafana image, latest)

2. All services must use `restart: unless-stopped` policy.

3. All services must connect to a shared Docker network named `starlink-net`.

4. The system must define the following named volumes:
   - `prometheus_data` → mounted to Prometheus data directory
   - `grafana_data` → mounted to Grafana data directory
   - `route_data` → mounted to `/data/routes/` (accessible to backend)
   - `sim_route_data` → mounted to `/data/sim_routes/` (accessible to backend)

5. Services must expose the following ports:
   - `starlink-location`: 8000 (FastAPI)
   - `prometheus`: 9090 (Prometheus UI)
   - `grafana`: 3000 (Grafana UI)

### 4.3 Starlink Location Service (Stub)

1. The `starlink-location` service must be built from a Dockerfile using
   `python:3.11-slim` base image.

1. The service must install FastAPI and uvicorn via `requirements.txt`.

1. The service must expose two HTTP endpoints:
   - `GET /health` → returns JSON `{"status": "ok"}`
   - `GET /metrics` → returns Prometheus-formatted text with
     `Content-Type: text/plain`

1. The `/metrics` endpoint must return valid Prometheus format including:

   ```text
   # HELP starlink_service_info Service information
   # TYPE starlink_service_info gauge
   starlink_service_info{version="0.1.0",mode="stub"} 1
   ```

1. The service must start via `uvicorn app:app --host 0.0.0.0 --port 8000`.

### 4.4 Prometheus Configuration

1. Prometheus must be configured to scrape the `starlink-location` service every
   15 seconds.

1. The `prometheus.yml` must define:
   - Global scrape interval: 15s
   - Scrape config for job `starlink-location` targeting
     `<http://starlink-location:8000/metrics`>

1. Prometheus must use the retention period defined in the
   `PROMETHEUS_RETENTION` environment variable.

### 4.5 Grafana Configuration

1. Grafana must be accessible at `<http://localhost:3000`.>

2. Grafana must use the admin password from `GRAFANA_ADMIN_PASSWORD` environment
   variable.

3. The `monitoring/grafana/provisioning/` directory structure must be created
   (empty for Phase 1, used in Phase 5).

### 4.6 Environment Configuration

1. The system must provide a `.env` file with the following variables:

   ```bash
   SIMULATION_MODE=true
   PROMETHEUS_RETENTION=15d
   GRAFANA_ADMIN_PASSWORD=admin
   STARLINK_LOCATION_PORT=8000
   PROMETHEUS_PORT=9090
   GRAFANA_PORT=3000
   ```

1. The system must provide an `.env.example` file with documented example
   values.

### 4.7 Version Control

1. The system must initialize a git repository (if not already initialized).

2. The system must provide a `.gitignore` file that excludes:
   - `.env` (but not `.env.example`)
   - Python cache files (`__pycache__/`, `*.pyc`)
   - Docker volumes (local data directories)
   - IDE-specific files (`.vscode/`, `.idea/`)

### 4.8 Documentation

1. The system must provide a `README.md` including:
   - Project overview and purpose
   - Quick start instructions (`docker compose up -d`)
   - Access points for all services
   - Link to architecture documentation
   - Development workflow basics

### 4.9 Validation & Testing

1. The system must provide a `test-phase1.sh` bash script that validates:
   - All three containers are running
   - Grafana UI responds with HTTP 200 at `<http://localhost:3000`>
   - Prometheus UI responds with HTTP 200 at `<http://localhost:9090`>
   - `/health` endpoint returns `{"status": "ok"}`
   - `/metrics` endpoint returns Prometheus-formatted text
   - Prometheus successfully scrapes the `starlink-location` target (visible in
     Prometheus targets page)

1. The test script must exit with code 0 on success, non-zero on failure.

1. The test script must output clear success/failure messages for each
   validation step.

---

## 5. Non-Goals (Out of Scope)

1. **Real Starlink Data Collection** - Phase 1 only creates stubs; actual
   telemetry collection is Phase 2+
1. **Simulation Engine** - Simulation logic is Phase 3
1. **Grafana Dashboards** - Dashboard creation is Phase 5
1. **KML/Route Processing** - Route handling is Phase 4
1. **Live Mode Integration** - Connection to real Starlink dish is Phase 7
1. **CI/CD Automation** - GitHub Actions workflows are Phase 8
1. **Production Hardening** - Security, TLS, auth improvements are post-Phase 8

---

## 6. Design Considerations

### Docker Image Selection

- **Backend**: `python:3.11-slim` provides a good balance between image size
  (~120MB) and compatibility while including build tools needed for future
  dependencies.
- **Prometheus/Grafana**: Using `latest` tags for rapid development; will pin
  versions in Phase 8 for production.

### Volume Strategy

- **Named Volumes**: Easier to manage, backup, and inspect compared to anonymous
  volumes.
- **Separate Data Directories**: Keeping `routes/` and `sim_routes/` separate
  allows clear distinction between production and simulation data.

### Network Configuration

- **Single Shared Network**: Simplifies service discovery and inter-container
  communication.
- **Default Bridge Driver**: Sufficient for single-host deployment; can migrate
  to overlay networks if multi-host support is needed.

### Stub Service Implementation

- **Minimal FastAPI**: Sets the pattern for Phase 2+ without over-engineering.
- **Prometheus Format**: Stub returns valid format to validate scraping logic
  before implementing real metrics.

---

## 7. Technical Considerations

### Dependencies

- Docker Engine 20.10+
- Docker Compose V2
- Git 2.30+
- Bash 4.0+ (for test script)
- `curl` or `wget` (for smoke tests)

### File Permissions

- Docker volumes must be readable/writable by container users
- Backend service should run as non-root user (add in Dockerfile)

### Port Conflicts

- If ports 3000, 8000, or 9090 are in use, the system should fail fast with
  clear error messages
- Consider documenting port customization via `.env`

### Cross-Platform Compatibility

- Line endings: Use `.gitattributes` to ensure LF line endings for shell scripts
- Paths: Use forward slashes in Docker Compose configs

---

## 8. Success Metrics

### Validation Criteria

1. **Infrastructure Success**: `docker compose up -d` completes without errors
2. **Service Health**: All three services show "healthy" or "running" status
3. **Network Connectivity**: Prometheus successfully scrapes `starlink-location`
4. **Data Persistence**: Stopping and restarting containers preserves Grafana
   settings
5. **Automated Testing**: `./test-phase1.sh` passes all checks
6. **Documentation Quality**: New contributor can set up environment in <5
   minutes

### Phase Completion Definition

Phase 1 is complete when:

- All functional requirements (4.1–4.9) are implemented
- The smoke test script passes 100% of checks
- README provides clear setup instructions
- Subsequent phases can begin development without infrastructure changes

---

## 9. Open Questions

1. **Python Version**: Should we target Python 3.11 specifically, or support
   3.10+?
   - **Recommendation**: Pin to 3.11-slim for consistency
1. **Grafana Plugins**: Should we pre-install map plugins in Phase 1, or wait
   until Phase 5?
   - **Recommendation**: Wait for Phase 5 to avoid bloat
1. **Logging Strategy**: Should we configure Docker logging drivers in Phase 1?
   - **Recommendation**: Use defaults (json-file) for Phase 1, optimize later
1. **Health Checks**: Should Docker Compose include health check definitions?
   - **Recommendation**: Add basic HTTP health checks for
     starlink-location/Grafana
1. **Development vs Production**: Should we separate `docker-compose.yml` and
   `docker-compose.prod.yml`?
   - **Recommendation**: Single file for Phase 1, split in Phase 8 if needed

---

## Acceptance Criteria Checklist

- [ ] Directory structure matches specification (4.1)
- [ ] `docker compose up -d` starts all three services
- [ ] Grafana accessible at <http://localhost:3000>
- [ ] Prometheus accessible at <http://localhost:9090>
- [ ] Backend `/health` returns `{"status": "ok"}`
- [ ] Backend `/metrics` returns Prometheus format
- [ ] Prometheus targets page shows `starlink-location` as UP
- [ ] Named volumes persist data across restarts
- [ ] `.env.example` provides clear documentation
- [ ] `.gitignore` prevents committing secrets
- [ ] `README.md` includes quick start guide
- [ ] `test-phase1.sh` validates all infrastructure
- [ ] Git repository initialized with initial commit
- [ ] All services use `restart: unless-stopped`
- [ ] No errors in `docker compose logs`

---

## Implementation Notes for Developers

### Suggested Development Order

1. Create directory structure
2. Initialize git repository and add `.gitignore`
3. Create `.env` and `.env.example`
4. Implement stub `starlink-location` service (Dockerfile, app.py,
   requirements.txt)
5. Configure `prometheus.yml`
6. Create `docker-compose.yml`
7. Write `README.md`
8. Implement `test-phase1.sh`
9. Validate end-to-end functionality
10. Create initial git commit

### Testing Strategy

After implementation, test in this order:

1. Build all images: `docker compose build`
2. Start stack: `docker compose up -d`
3. Check logs: `docker compose logs`
4. Run smoke tests: `./test-phase1.sh`
5. Manually verify each service UI
6. Test container restart: `docker compose restart`
7. Test persistence: `docker compose down && docker compose up -d`

### Common Pitfalls

- **Port Conflicts**: Ensure ports 3000, 8000, 9090 are free before starting
- **Volume Permissions**: Grafana may need explicit user permissions in
  Dockerfile
- **Network Timing**: Prometheus may initially show target as "down" until
  backend fully starts (use health checks)
- **Environment Variables**: Ensure `.env` is loaded by Docker Compose (check
  with `docker compose config`)

---

**End of PRD**
