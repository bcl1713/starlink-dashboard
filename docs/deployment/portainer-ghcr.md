# Portainer GHCR Deployment Runbook

This runbook defines the supported deployment contract for the dedicated
Portainer/GitHub Container Registry (GHCR) profile tracked by
[issue #121](https://github.com/bcl1713/starlink-dashboard/issues/121).

It supports review and authorized non-live validation only. It does not
authorize a Portainer, DNS, proxy, volume, credential, public-host, or live
environment operation.

## Deployment Profiles Are Separate

The root `docker-compose.yml` and `.env.example` remain the repository-managed
local developer workflow. Local development builds from the checkout and loads
its local `.env` configuration; do not replace that workflow with this runbook.

The dedicated `deployment/portainer-ghcr-compose.yml` is a Portainer Git-stack
template. It uses GHCR `image:` references, does not use local `build:`
contexts, and intentionally does not load a repository `.env` file. Portainer
holds its runtime configuration and secrets.

## Deployment Contract

The Portainer template has these invariants:

- Select all application and monitoring images with the one immutable
  `STARLINK_IMAGE_TAG` value. Use a reviewed SHA-derived tag or versioned
  release tag, never a mutable tag such as `latest`.
- The backend, Mission Planner, GFS worker and Prometheus use GHCR images from
  the same immutable selection.
- Prometheus rules/configuration are baked into its monitoring image. The
  Portainer template must not mount repository-relative `monitoring/` paths.
- The template joins the pre-existing external `proxy` network without creating
  or reconfiguring it. Its stable aliases are `starlink-location`, `prometheus`,
  and `mission-planner`.
- Mission Planner remains reachable through its proxy route. Its dashboard and
  `/api/v2/missions` API are expected to work from the same origin; do not
  substitute direct container or host-port routing.
- Simulation remains the non-live default. A live mode change is outside this
  runbook and requires the [live rollout gate](#live-rollout-gate).

The GHCR publishing workflow produces the required application and monitoring
images for each supported immutable selection. Operators must not replace the
reviewed image selections with arbitrary upstream image references.

## Portainer-Supplied Configuration

Enter stack configuration in Portainer, not in a checked-out `.env` file. Use
placeholders in change records and documentation; never record live paths,
volume names, or credentials in the repository.

The following host-path keys are required and fail closed when missing:

| Key                             | Persistent category             |
| ------------------------------- | ------------------------------- |
| `STARLINK_APP_DATA_PATH`        | Application-managed data        |
| `STARLINK_ROUTE_DATA_PATH`      | Route and simulation-route data |
| `STARLINK_PROMETHEUS_DATA_PATH` | Prometheus time-series data     |

The template binds these host paths to the containers. Supply existing,
authorized persistent locations with appropriate service permissions. Do not
create, delete, relocate, or disclose live paths while following this runbook.

Other stack settings remain Portainer-managed. For non-live work, retain
`STARLINK_MODE=simulation`.

`STARLINK_PROMETHEUS_URL` defaults to `http://prometheus:9090`, the stable
Prometheus service alias in this profile. `STARLINK_HISTORY_WINDOW_SECONDS` is
an optional bootstrap default for the Mission Planner overview query lookback.
After an operator selects a window in the dashboard, the persisted dashboard
selection takes precedence and is stored under
`STARLINK_APP_DATA_PATH/settings/overview-history.json`. This display/query
window is independent of Prometheus database retention (`PROMETHEUS_RETENTION`).

## NOAA GFS Weather

Both `deployment/portainer-ghcr-compose.yml` and the Forge variant
`deployment/portainer-forge-dev-compose.yml` include the private `gfs-worker`
service. Select a tag that provides all four images: backend, Mission Planner,
Prometheus and GFS worker. The publishing workflow builds the worker from
`backend/starlink-location/Dockerfile.gfs` and inventories its GHCR versions
alongside the other packages.

No additional host-path key is required. The worker reads aviation settings from
the existing `STARLINK_APP_DATA_PATH/settings` directory through a read-only
mount. Project-scoped `gfs_products` and `gfs_mailbox` named volumes share
normalized products and control records with the API; the API mounts products
read-only. Retain these volumes across redeployments and restarts: they also
preserve request quotas and product admission clocks. Keep the stack project
identity stable and do not use `down --volumes` for a retained installation.

The worker has no published port or proxy alias and joins only the private
application network. It retains one CPU and a 1 GiB memory limit, an init
process and a fifteen-second shutdown grace period. Its restart policy matches
the on-demand stack. Winds and temperature remain default off in Configuration;
without active model demand, the worker performs no NOAA acquisition.

For non-live verification, confirm all four services start, then enable winds
and temperature in Configuration and select FL300 with a +3 h horizon. Keep
Overview visible while acquisition completes. Its same-origin aviation catalog
should admit both products, and the expanded NOAA GFS status should show the
actual model run and valid time. Confirm settings and model availability survive
a stack restart using the same project and persisted data. Missing or failed
model data remains unknown weather; core dashboard health remains independent.

## Overview Data Link Persistence

The independent Configuration switches **Starshield data link** and **X-band
data link** default to enabled. **Orbital traffic view** defaults to disabled.
The backend persists shared panel and map-layer preferences under
`STARLINK_APP_DATA_PATH/settings/overview-links.json`; the existing
application-data mount supplies persistence, with no additional volume or
bootstrap environment variable. Preserve this category during updates/rollback
and ensure the service user can write its settings directory.

The **Aircraft history** switch defaults to `true` and controls the flown track
and its legend entry without disabling history collection or network graphs.
Existing saved files missing `aircraft_history_enabled` default to enabled.

Same-origin `GET /api/overview-links/settings` returns all 21 boolean fields;
partial `PUT` merges only supplied fields. Missing saved fields use defaults;
unfamiliar saved fields survive reads and partial saves, preserving preferences
across compatible schema upgrades and future rollbacks. A deployed version must
include this compatibility reader to accept fields introduced by a newer
version. Retain the settings file when redeploying; manual removal is
unnecessary for additive schema changes. Malformed JSON or invalid recognized
values still require repair and are never silently reset.

In an isolated non-live acceptance project, save all four combinations, restart
only that project's backend, and confirm each pair survives through the
frontend's Nginx API path. Keep its ports and persisted data separate from
existing installations. A visibility save must not change measured
status/history or configured warning behavior. Starshield particles use measured
traffic; X-band's 4/4 Mbps, 500 ms rendering preset is illustrative and never
persisted as observed telemetry.

## Select an Immutable Release and Rollback Target

Before an authorized non-live update:

1. Select a reviewed immutable SHA-derived or versioned release tag.
2. Record the current immutable tag and the intended replacement in the approved
   change record. The current tag is the rollback selection.
3. Verify that the selected GHCR images correspond to the reviewed source
   revision and include the backend, Mission Planner, Prometheus and GFS worker
   images.
4. Verify the Git-stack template uses the three required host-path keys, the
   external `proxy` network, stable aliases, and no repository-relative
   monitoring mounts.
5. Confirm that required persistent locations already exist and that Portainer,
   rather than the repository, holds configuration and secrets.

Stop if the selection is mutable, the rollback target is unknown, a required
host-path key is absent, or the template depends on repository-local monitoring
files.

## Authorized Non-Live Stack Update

For an authorized non-live Portainer Git-stack update:

1. Select the reviewed repository reference and the dedicated Portainer GHCR
   template path.
2. Set `STARLINK_IMAGE_TAG` to the approved immutable selection and provide all
   three required host-path keys in Portainer.
3. Enable image pulling so Portainer obtains the chosen immutable images.
4. Leave image pruning disabled. Pull without prune preserves the prior image
   selection for rollback.
5. Review the rendered template before submitting it. It must use GHCR images,
   baked monitoring configuration, the external `proxy` network, and the three
   stable aliases.
6. Perform only the approved non-live validation. Do not change DNS, proxy
   routing, persistent storage, credentials, or public hosts.

These steps describe an operational contract; they do not grant permission to
operate a Portainer environment.

## Non-Live Verification

Run verification only in an isolated, authorized non-live environment. Query
services through the external proxy aliases and confirm all of the following:

```text
http://starlink-location:8000/health
http://prometheus:9090/-/ready
http://mission-planner/
http://mission-planner/api/v2/missions
```

The first two probes verify backend health and Prometheus readiness. The final
two verify the Mission Planner dashboard route and its same-origin API behavior.
Record only pass/fail results and the immutable image selection; never include
environment addresses, paths, credentials, or storage identifiers in the
repository.

## Rollback

If an authorized non-live update fails, set `STARLINK_IMAGE_TAG` back to the
recorded prior immutable selection and use the matching Git-stack template
revision. Tags published before GFS worker support have only three images;
rollback to those tags requires their earlier template without the worker
service. Retain the GFS volumes so a later update can reuse them. Use the same
Git-stack update flow:

- keep image pulling enabled so the known-good selection can be retrieved
- keep image pruning disabled so rollback images remain available
- preserve all three host-path categories and the GFS named volumes
- preserve the external `proxy` network, aliases, and same-origin routing

Do not roll back by using `latest`, recreating persistent storage, replacing
host paths, or making manual DNS/proxy changes.

## Clean-Deployment Gates

An authorized non-live deployment may proceed only when all of these are true:

1. The implementation and this documentation have passed independent review.
2. The docs PR has merged to `dev` before the implementation PR is merged.
3. An immutable selection and rollback selection are recorded.
4. Required host-path keys are present and persistent storage is expected to be
   retained.
5. The rendered template passes the deployment-contract checks and non-live
   probes without repository-relative monitoring mounts.

## Live Rollout Gate

Live rollout is Brian-only. It requires Brian's explicit approval after the
clean-deployment gates pass. Workers must stop before any live rollout,
Portainer operation, DNS/proxy change, persistent-storage operation, credential
handling, or public-host verification.

## Completion Record

The approved change record may contain only non-sensitive evidence:

- selected immutable tag and recorded rollback tag
- confirmation that pulling was enabled and pruning was disabled
- confirmation that all three host-path categories were supplied and retained
- non-live probe pass/fail outcomes
- confirmation that external-proxy aliases and Mission Planner same-origin
  behavior were preserved
- Brian's explicit live approval, if a separate live rollout is authorized

For repository-managed local development, use the
[Setup guide](../setup/README.md) instead. This runbook applies only to the
dedicated Portainer GHCR template.
