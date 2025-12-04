# Task List: Project Scaffolding (Phase 1)

Based on PRD: `0001-prd-project-scaffolding.md`

## Relevant Files

- `.gitignore` - Git ignore patterns for Python, Docker, IDE files, and secrets
- `.gitattributes` - Ensures LF line endings for shell scripts cross-platform
- `.env` - Local environment variables (gitignored, created by developer)
- `.env.example` - Example environment configuration with documentation
- `backend/starlink-location/app.py` - Stub FastAPI application with /health and
  /metrics endpoints
- `backend/starlink-location/Dockerfile` - Multi-stage Docker image for Python
  service
- `backend/starlink-location/requirements.txt` - Python dependencies (FastAPI,
  uvicorn, prometheus-client)
- `monitoring/prometheus/prometheus.yml` - Prometheus scrape configuration
- `docker-compose.yml` - Orchestration config for all three services with
  networking and volumes
- `README.md` - Project documentation with quick start guide
- `test-phase1.sh` - Automated smoke test script for validating infrastructure

### Notes

- No test files are needed for Phase 1 since we're only scaffolding
  infrastructure
- The stub backend service will be expanded in Phase 2+ with actual
  functionality and tests
- Directory structure will be created as part of the tasks (e.g.,
  `data/routes/`, `data/sim_routes/`, `.github/workflows/`,
  `monitoring/grafana/provisioning/`)

## Tasks

- [x] 1.0 Initialize version control and project structure
  - [x] 1.1 Create complete directory structure (backend/, monitoring/, data/,
        .github/workflows/)
  - [x] 1.2 Create subdirectories: backend/starlink-location/,
        monitoring/prometheus/, monitoring/grafana/provisioning/, data/routes/,
        data/sim_routes/
  - [x] 1.3 Initialize git repository with `git init`
  - [x] 1.4 Create `.gitignore` file with patterns for Python (**pycache**,
        `*.pyc`, `*.pyo`, `*.pyd`, .Python, env/, venv/), Docker (data/,
        volumes/), IDE (.vscode/, .idea/, `*.swp`), and secrets (.env)
  - [x] 1.5 Create `.gitattributes` with `*.sh text eol=lf` to ensure shell
        scripts use LF line endings
  - [x] 1.6 Create `.env.example` with documented environment variables:
        SIMULATION_MODE, PROMETHEUS_RETENTION, GRAFANA_ADMIN_PASSWORD,
        STARLINK_LOCATION_PORT, PROMETHEUS_PORT, GRAFANA_PORT
  - [x] 1.7 Copy `.env.example` to `.env` for local development

- [x] 2.0 Create stub backend service (starlink-location)
  - [x] 2.1 Create `backend/starlink-location/requirements.txt` with
        dependencies: fastapi>=0.104.0, uvicorn[standard]>=0.24.0,
        prometheus-client>=0.19.0
  - [x] 2.2 Create `backend/starlink-location/app.py` with FastAPI application
        skeleton
  - [x] 2.3 Implement `GET /health` endpoint returning `{"status": "ok"}` with
        200 status code
  - [x] 2.4 Implement `GET /metrics` endpoint using prometheus_client to return
        Prometheus-formatted text with Content-Type: text/plain
  - [x] 2.5 Add `starlink_service_info` gauge metric with labels version="0.1.0"
        and mode="stub", set to value 1
  - [x] 2.6 Create `backend/starlink-location/Dockerfile` using python:3.11-slim
        base image
  - [x] 2.7 In Dockerfile: set working directory to /app, copy requirements.txt,
        run pip install, copy app.py, expose port 8000
  - [x] 2.8 In Dockerfile: create non-root user 'appuser' and switch to it for
        security
  - [x] 2.9 Set Dockerfile CMD to:
        `["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]`

- [x] 3.0 Configure monitoring stack (Prometheus and Grafana)
  - [x] 3.1 Create `monitoring/prometheus/prometheus.yml` with global
        scrape_interval: 15s and evaluation_interval: 15s
  - [x] 3.2 Add scrape_configs section with job_name: 'starlink-location'
  - [x] 3.3 Configure scrape job to target 'starlink-location:8000' with
        metrics_path: '/metrics' and scrape_interval: 15s
  - [x] 3.4 Create empty `monitoring/grafana/provisioning/datasources/`
        directory (for Phase 5)
  - [x] 3.5 Create empty `monitoring/grafana/provisioning/dashboards/` directory
        (for Phase 5)

- [x] 4.0 Create Docker Compose orchestration
  - [x] 4.1 Create `docker-compose.yml` with version and services sections
  - [x] 4.2 Define `starlink-location` service: build from
        backend/starlink-location/, map port ${STARLINK_LOCATION_PORT}:8000,
        restart: unless-stopped
  - [x] 4.3 Add healthcheck to starlink-location service: test curl --fail
        <http://localhost:8000/health> every 30s with 3 retries
  - [x] 4.4 Mount volumes to starlink-location: route_data:/data/routes and
        sim_route_data:/data/sim_routes
  - [x] 4.5 Define `prometheus` service: image prom/prometheus:latest, map port
        ${PROMETHEUS_PORT}:9090, restart: unless-stopped
  - [x] 4.6 Mount prometheus.yml to /etc/prometheus/prometheus.yml and
        prometheus_data to /prometheus
  - [x] 4.7 Add command to prometheus:
        --config.file=/etc/prometheus/prometheus.yml
        --storage.tsdb.retention.time=${PROMETHEUS_RETENTION}
  - [x] 4.8 Add depends_on to prometheus service to wait for starlink-location
        service health
  - [x] 4.9 Define `grafana` service: image grafana/grafana:latest, map port
        ${GRAFANA_PORT}:3000, restart: unless-stopped
  - [x] 4.10 Set Grafana environment variables:
        GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD},
        GF_USERS_ALLOW_SIGN_UP=false
  - [x] 4.11 Mount grafana_data to /var/lib/grafana and
        monitoring/grafana/provisioning to /etc/grafana/provisioning
  - [x] 4.12 Add depends_on to grafana service to wait for prometheus
  - [x] 4.13 Define networks section with starlink-net using bridge driver
  - [x] 4.14 Add starlink-net network to all three services
  - [x] 4.15 Define volumes section with named volumes: prometheus_data,
        grafana_data, route_data, sim_route_data
  - [x] 4.16 Add env_file: .env to docker-compose.yml to load environment
        variables

- [x] 5.0 Write project documentation and validation scripts
  - [x] 5.1 Create `README.md` with project title and overview paragraph
        describing the Starlink monitoring system
  - [x] 5.2 Add "Quick Start" section with prerequisites (Docker, Docker
        Compose, Git) and version requirements
  - [x] 5.3 Add step-by-step setup instructions: clone repo, copy .env.example
        to .env, run docker compose up -d
  - [x] 5.4 Add "Access Points" section listing all service URLs: Grafana
        (localhost:3000), Prometheus (localhost:9090), Backend (localhost:8000)
  - [x] 5.5 Add "Configuration" section explaining .env variables and how to
        customize them
  - [x] 5.6 Add "Development Workflow" section with common Docker Compose
        commands (up, down, logs, restart, build)
  - [x] 5.7 Add "Architecture" section with link to docs/design-document.md and
        brief component descriptions
  - [x] 5.8 Add "Testing" section explaining how to run test-phase1.sh and what
        it validates
  - [x] 5.9 Create `test-phase1.sh` with bash shebang and set -e for error
        handling
  - [x] 5.10 Add test functions to check: containers running (docker compose
        ps), Grafana HTTP 200 (curl localhost:3000), Prometheus HTTP 200 (curl
        localhost:9090)
  - [x] 5.11 Add test functions for backend: /health returns {"status":"ok"},
        /metrics returns text containing "starlink_service_info"
  - [x] 5.12 Add test to check Prometheus targets page shows starlink-location
        as UP (query Prometheus API at /api/v1/targets)
  - [x] 5.13 Add colored output to test script: green for PASS, red for FAIL,
        with clear messages for each check
  - [x] 5.14 Make test-phase1.sh executable with `chmod +x test-phase1.sh`
  - [x] 5.15 Add final summary at end of script showing total passed/failed
        tests and exit with appropriate code
