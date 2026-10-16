# Documentation Index

These guides describe the checked-out code. The latest released baseline is
**v1.0.0**; [release notes](release-notes.md) distinguish it from subsequent
`dev` changes. Use the guide for the version you deploy.

## Install and Operate

- [Quick start](setup/quick-start.md), [installation](setup/installation.md),
  and [configuration](setup/configuration.md)
- [Feature catalog](features/overview.md) and
  [Overview weather](features/overview-weather.md)
- [Mission planning](missions/mission-planning-guide.md),
  [itinerary intake](missions/itinerary-planning.md), and
  [mission packages](missions/mission-package-import.md)
- [Troubleshooting](troubleshooting/README.md) and
  [monitoring](../monitoring/README.md)
- [Portainer/GHCR deployment](deployment/portainer-ghcr.md)

## Integrate and Contribute

- [API reference](api-reference-index.md); running backend `/docs` and
  `/openapi.json` describe that deployment's actual schema
- [Architecture](architecture/README.md) and
  [data structures](data-structures/index.md)
- [Contributing](../CONTRIBUTING.md), [workflow](development/workflow.md),
  [quality gates](contributing/quality-gates.md), and
  [release policy](development/release-policy.md)
- [Managed-cloud Docker](development/cloud-docker.md) and
  [acceptance platform](operations/acceptance-platform.md)

## Documentation Status

Current guides live in setup, features, missions, API, architecture,
development, and troubleshooting. Older index URLs remain as navigation entry
points.

[Reports](reports/README.md), `docs/superpowers/specs/`, and
`docs/superpowers/plans/` retain dated designs, work records, and acceptance
results. Historical test counts, old paths, screenshots, and proposed behavior
in these records describe their original candidate, not today's release. The
[original development plan](development-plan.md) and
[early feature history](completed-features.md) are historical too.

When behavior changes, update the affected current guide, category index, and
release notes in the same PR. Verify documented names and defaults against
source and `.env.example`; run documentation lint and links through the
[quality gates](contributing/quality-gates.md).
