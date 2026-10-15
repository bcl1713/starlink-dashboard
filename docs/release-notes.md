# Release Baseline and Development Changes

## v1.0.0

The `v1.0.0` tag points to `3728280a` (release PR #335). Use the versioned
repository documentation and generated `/docs` for the version you run. This
documentation refresh corrects stale pre-release guidance; it does not create a
new application release.

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

## Changes on `dev` After v1.0.0

These changes require a later checked-out commit or image than the v1.0.0 tag:

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
