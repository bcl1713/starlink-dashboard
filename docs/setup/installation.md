# Installation

Run these commands from a checkout of the version you intend to deploy. For
contributions, follow the isolated-worktree
[development workflow](../development/workflow.md).

## Requirements

Use Git, a working Docker Engine or Docker Desktop, and Docker Compose v2
(`docker compose version`). Docker must support the Compose options in the
checked-out file. Check [system requirements](system-requirements.md) first.

```bash
git clone https://github.com/bcl1713/starlink-dashboard.git
cd starlink-dashboard
git checkout v2.0.0
cp .env.example .env
./scripts/compose.sh config --quiet
./scripts/compose.sh up -d --build
```

The example pins the v2.0.0 release. Choose `dev` explicitly for newer
features and use its matching documentation; see
[release notes](../release-notes.md).

Keep `.env` local. The supplied example selects simulation and requires no dish.
The wrapper supplies the checked-out commit SHA required by image builds; use it
for build commands rather than bare `docker compose build`.

The backend and GFS worker build scientific Python dependencies; the frontend
builds its static bundle. Initial image builds need network access and can take
several minutes. The GFS worker is included automatically and remains idle when
there is no weather catalog demand.

## Access and verify

Default local URLs (backend and Prometheus host ports can change in `.env`):

| Service                   | URL                            |
| ------------------------- | ------------------------------ |
| Mission Planner           | <http://localhost:5173>        |
| Backend API documentation | <http://localhost:8000/docs>   |
| Backend health            | <http://localhost:8000/health> |
| Prometheus                | <http://localhost:9090>        |

Follow [installation verification](installation-verification.md). The backend
healthcheck permits a 90-second startup period; Prometheus waits for backend
health. A running container alone does not establish dish connectivity.

## Apply changes and stop

After changing `.env`, recreate the affected services; `restart` does not reload
container environment variables:

```bash
./scripts/compose.sh up -d
```

After pulling code or editing baked-in configuration, rebuild:

```bash
./scripts/compose.sh up -d --build
```

Stop this installation with `docker compose down`. Do not add `--volumes` when
you need retained routes, POIs, weather records, or metrics. See
[storage configuration](configuration/storage-configuration.md).
