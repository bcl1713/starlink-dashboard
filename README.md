# Starlink Dashboard

Starlink terminal monitoring and mission communication planning, with a native
3D Overview, live telemetry, route simulation, and reviewed mission exports. The
Docker stack runs Mission Planner, a FastAPI backend, Prometheus, and an
optional-demand NOAA GFS processing worker.

**Latest released baseline: v1.0.0.** These documents describe the checked-out
branch. `dev` also includes changes after that release; see the
[release baseline](docs/release-notes.md) before deploying or integrating.

## Quick Start

Install Git, Docker Engine or Docker Desktop, and Docker Compose v2. Start in
simulation mode without a Starlink terminal:

```bash
git clone https://github.com/bcl1713/starlink-dashboard.git
cd starlink-dashboard
git checkout v1.0.0
cp .env.example .env
./scripts/compose.sh up -d --build
curl --fail http://localhost:8000/health
```

Open Mission Planner at <http://localhost:5173>. Initial image builds and
service readiness take time; follow the [setup guide](docs/setup/quick-start.md)
for prerequisites, verification, live hardware, and troubleshooting. To try
integration changes instead, check out `dev` before building.

## What You Can Do

- Monitor position, connectivity, latency, throughput, and telemetry history on
  the responsive native Overview globe.
- Import KML routes, manage POIs, inspect route-aware ETAs, and replay mission
  legs at selectable simulation speeds.
- Create missions and legs, plan X-band/Starshield availability, review outages
  and backup gaps, and export mission packages and customer briefings.
- Enable precipitation radar, aviation bulletins and METARs, GFS flight-level
  winds/temperature, ADS-B aircraft, or orbital traffic in Configuration.
  External layers have independent coverage, freshness, and network limits.
- Keep multiple Overview displays aligned through shared persisted settings.

See the [feature catalog](docs/features/overview.md) and
[mission guide](docs/missions/mission-planning-guide.md) for workflows and
limits.

## Access Points

| Service         | Default URL                     | Purpose                              |
| --------------- | ------------------------------- | ------------------------------------ |
| Mission Planner | <http://localhost:5173>         | Overview, planning and configuration |
| Backend API     | <http://localhost:8000/docs>    | Generated interactive API reference  |
| Health          | <http://localhost:8000/health>  | Backend readiness                    |
| Metrics         | <http://localhost:8000/metrics> | Prometheus exposition                |
| Prometheus      | <http://localhost:9090>         | Metrics queries and retention        |

Ports above are defaults; backend and Prometheus mappings are configured in
`.env`. Keep deployment access restricted to your intended network. See
[deployment guidance](docs/deployment/portainer-ghcr.md) for hosted images.

## Configuration and Updates

Copy [.env.example](.env.example) for mode, hardware, ports, and retention.
`STARLINK_MODE=simulation` is the default; use `live` for terminal telemetry.
Operational clocks, weather, traffic, and display preferences are configured in
Mission Planner Configuration and persisted by the backend.

After moving to the desired reviewed commit or release, rebuild with:

```bash
./scripts/compose.sh up -d --build --remove-orphans
```

The wrapper supplies the checked-out commit SHA to image builds. It includes the
GFS worker, which stays idle without model-weather demand. Winds and temperature
start disabled. Updating an older stack removes the retired Grafana container;
its old volume is retained. Back up persistent mission, settings, route, POI,
and metrics data before updating; see
[storage configuration](docs/setup/configuration/storage-configuration.md).

## Documentation

- [Documentation index](docs/index.md): current guides and historical records
- [Setup](docs/setup/README.md) and
  [troubleshooting](docs/troubleshooting/quick-diagnostics.md)
- [Mission planning](docs/missions/README.md),
  [itinerary imports](docs/missions/itinerary-planning.md), and
  [weather](docs/features/overview-weather.md)
- [API reference](docs/api-reference-index.md) and
  [architecture](docs/architecture/README.md)
- [Contributing](CONTRIBUTING.md),
  [quality gates](docs/contributing/quality-gates.md), and
  [development workflow](docs/development/workflow.md)
- [Release policy](docs/development/release-policy.md) and
  [release baseline](docs/release-notes.md)

Dated reports and implementation plans preserve historical evidence. They are
not current installation or operator instructions.
