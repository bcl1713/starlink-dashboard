# Release Notes

## v3.0.0

This release promotes the Operator workspace, durable flight telemetry and
Starshield transition planning from `dev` since v2.0.0.

### v3 Compatibility and Upgrade

This is a major release because Operator is now the default workspace and the
legacy Operator page has been retired. Use the
[Operator user guide](operations/operator-user-guide.md) and
[quick reference](operations/operator-quick-reference.md) for the current
workflow. Set `OPERATOR_ENABLED=false` to disable Operator when required.

Deploy backend and frontend together. Back up persistent mission, route,
Operator, weather and monitoring storage before upgrading; include
`OPERATOR_ROOT/transport-catalog.json` with the Operator volume backup.
Existing Operator databases require the explicit maintenance CLI upgrade to
schema 003; startup never silently upgrades them. Stop the relevant writer and
follow the [journal maintenance guide](operations/operator-journal.md) and
[transport deployment guide](operations/operator-transport.md). Older binaries
reject upgraded databases: rollback requires the previous application and its
matching pre-upgrade backup. Preserve newer records separately before restore.

The v2 itinerary conversion and v1 API boundaries still apply: `/api/missions`
returns 404; use `/api/v2/missions` and route-bound leg activation. Flat v1
mission artifacts remain retained but inert, with no automatic migration or
cleanup. This release introduces no automatic reverse conversion.

After all four GHCR image builds succeed, pin
`STARLINK_IMAGE_TAG=v3.0.0`, or check out `v3.0.0` and run
`./scripts/compose.sh up -d --build --remove-orphans`.

### v3 Highlights

- Default responsive Operator workspace with durable journal history, recovery,
  communications requirements, conferences, issues and manual capabilities.
- Reported transport assignments with managed service/transport catalogs;
  Apply records an operator report and does not command routing equipment.
- Overview controls, saved presets, guided mission procedures and packaged help.
- Durable mission flight events and telemetry, plus predicted Starshield PoP
  transition advisories and planning windows with fallback-aware protection.
- Improved Overview framing and fullscreen layout, mobile controls, and stable
  transition timing across telemetry updates.

### v3 Validation and Limits

Merged changes retain production browser, backend, migration and recovery
evidence in the [Operator workspace report](reports/2026-10-18-operator-workspace)
and linked feature PRs, including
[default workspace acceptance](https://github.com/bcl1713/starlink-dashboard/pull/384)
and [transition timing correction](https://github.com/bcl1713/starlink-dashboard/pull/386).
Release PR checks must pass before promotion. Synthetic software acceptance does
not establish aircraft readiness, provider availability or hardware performance.
This release preparation adds no aircraft validation or live deployment.

## v2.0.0

This release promotes the validated SIGMET, itinerary import, offline
Configuration and responsive Overview changes from `dev` since v1.0.0.

### Compatibility and Upgrade

This is a major release because itinerary imports now create ordinary editable
missions and automatically apply source revisions, replacing the separate JSON
review/publication workflow. Incoming source fields win when they conflict with
manual edits; compatible edits and revision history are retained. KML timestamps
are authoritative and AR windows follow departure/arrival offsets. Review the
[import workflow](missions/itinerary-planning.md) before updating saved imports.
Newly imported missions remain inactive until normal leg activation.

At startup, existing itinerary-planning missions are persistently converted to
ordinary missions with import provenance; installed legs and source records are
retained, and unfinished legs are retained as pending evidence. Back up mission
storage before the first v2 start. An image-only downgrade does not restore the
v1 itinerary workflow: rollback requires the matching pre-upgrade mission-data
backup as well as the old images. Preserve newer data separately before any
restore; no reverse conversion is supplied.

Deploy backend and frontend together: the strict SIGMET read contract is
`route-sigmets-v2`. Back up persistent application, route and monitoring data,
including GFS volumes, before upgrading. Pin all four GHCR images to
`STARLINK_IMAGE_TAG=v2.0.0` after tag publishing succeeds, or check out `v2.0.0`
and run `./scripts/compose.sh up -d --build --remove-orphans`.

The v1 compatibility boundary still applies: `/api/missions` returns 404; use
`/api/v2/missions` and route-bound leg activation. Flat v1 mission artifacts
remain retained but inert, with no automatic migration or cleanup. Customer PDF
enablement remains a separate operator decision.

### Highlights

- Route-linked SIGMET advisories, shared acknowledgements/manual selections,
  POI-style globe labels, planned passage windows and live crossing estimates.
- Ordinary editable itinerary missions, automatic revisions, revision history,
  chronological legs and consistent CSV/PDF exports.
- Local Configuration remains usable when optional online resources fail.
- Overview fills the viewport with translucent panels, responsive scrolling,
  route-aware globe framing and corrected fullscreen zoom.
- Documentation refreshed for current APIs, deployment and operator workflows.

### Validation and Limits

The merged feature records include production Docker/Nginx browser acceptance
for SIGMETs, ordinary itinerary imports and responsive/fullscreen Overview.
PR #343 records 3,412 passing backend tests (20 skips), 1,652 passing frontend
tests, a production build and exact-commit import/edit/revision/export controls.
PR #345 records 1,652 passing frontend tests and responsive/fullscreen production
browser checks. The documentation refresh passed all three CI quality gates.
Release PR checks rerun the full CI gates before promotion.

See the [SIGMET evidence](reports/2026-10-15-sigmet-live-eta.md),
[itinerary PR](https://github.com/bcl1713/starlink-dashboard/pull/343),
[Overview PR](https://github.com/bcl1713/starlink-dashboard/pull/345) and
[documentation audit](reports/2026-10-15-documentation-refresh.md).
Wind acceptance was closed by owner confirmation in PR #342. Synthetic/pinned
weather controls do not establish current provider availability or workstation
hardware performance. This release preparation adds no new aircraft validation
or live deployment; backend version metadata still contains historical values.

Use a consistent stopped-service backup; see
[storage backup guidance](setup/configuration/storage-configuration.md).

## v1.0.0

The `v1.0.0` tag points to `3728280a` (release PR #335). Use the versioned
repository documentation and generated `/docs` for the version you run. The
documentation refresh corrects stale pre-release guidance.

The release includes the native Mission Planner Overview, telemetry history, KML
routes and POIs, Mission V2 leg planning and simulation, itinerary planning,
reviewed exports/customer briefings, aviation weather and GFS flight-level
winds/temperature, ADS-B and orbital layers. External feeds remain optional and
subject to their coverage, freshness, and connectivity limits.

Mission V2 replaces the retired flat mission API: `/api/missions` is removed and
returns 404. Flat v1 mission artifacts remain retained but inert, with no
automatic migration or cleanup. Use `/api/v2/missions` and leg activation; see
[mission packages](missions/mission-package-import.md) before importing old
data. Grafana is retired from the bundled stack; Mission Planner is the operator
interface.

## Changes Included Since v1.0.0

- **#337–339:** route-linked SIGMET matching, shared acknowledgements and manual
  selections, concise attention and globe review, and POI-style callout labels.
- **#340:** planned SIGMET passage timing and live flight crossing estimates,
  including unknown/stale telemetry handling and ordered multi-display results.
  The strict read payload is `route-sigmets-v2`; deploy its backend and frontend
  together. [Timing contract](api/route-sigmet-timing.md).
- **#341:** local Configuration remains usable without optional online
  resources.
- **#342:** wind acceptance documentation closed by owner confirmation; this is
  a verification record, not a new wind feature.
- **#345:** responsive full-viewport Overview, scrolling panels, route framing
  and fullscreen zoom corrections.
- **#343:** itinerary intake creates ordinary editable missions. Source updates
  apply conflicting incoming source fields automatically while retaining
  compatible manual edits; mission views and exports use effective departure
  order. [Current itinerary workflow](missions/itinerary-planning.md).

## Update Safely

Back up persistent data before updating. Select the reviewed tag or commit, then
use `./scripts/compose.sh up -d --build --remove-orphans` from repository root.
For GHCR, pin all service images to the same release or full commit SHA; see
[deployment](deployment/portainer-ghcr.md). Do not mix backend/frontend versions
when strict contracts change.

Confirm health, telemetry mode, mission leg selection, and your required export
and display workflows after an update. Synthetic acceptance evidence does not
establish live provider availability or aircraft workstation performance.

Future release PRs should extend this page with operator-visible changes,
compatibility requirements, and validation performed. Follow the
[release policy](development/release-policy.md).
