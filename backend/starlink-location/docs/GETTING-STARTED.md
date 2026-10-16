# Getting Started with the Backend

Use the maintained [setup guide](../../../docs/setup/quick-start.md) to create
`.env` and build the complete stack from repository root:

```bash
./scripts/compose.sh up -d --build
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/api/status
```

The running service exposes `/docs`, `/openapi.json`, and `/metrics`. Consult
its generated schema for response fields; a deployment's internal service
version string is not a substitute for its release tag or image commit SHA.

For isolated backend reload, Vite proxy integration, focused checks, production
acceptance, and teardown, follow the
[development workflow](../../../docs/development/workflow.md). The backend entry
point is `main:app` from `backend/starlink-location`. The production Docker
build uses repository root as its context; prefer the Compose wrapper, which
supplies the required candidate SHA and shared storage configuration.

Configuration comes from the checked-out configuration model and deployment
environment. See [configuration](../../../docs/setup/configuration.md) and
[API reference](../../../docs/api-reference-index.md) for current interfaces.

[Back to backend](../README.md)
