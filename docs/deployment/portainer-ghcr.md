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
- The backend and Mission Planner use their GHCR application images. Prometheus
  and Grafana also use GHCR images built for this profile.
- Prometheus rules/configuration and Grafana provisioning/customization are
  baked into those monitoring images. The Portainer template must not mount
  repository-relative `monitoring/` paths.
- The template joins the pre-existing external `proxy` network without creating
  or reconfiguring it. Its stable aliases are `starlink-location`, `prometheus`,
  `grafana`, and `mission-planner`.
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
| `STARLINK_GRAFANA_DATA_PATH`    | Grafana state and dashboards    |

The template binds these host paths to the containers. Supply existing,
authorized persistent locations with appropriate service permissions. Do not
create, delete, relocate, or disclose live paths while following this runbook.

Other stack settings remain Portainer-managed. `GRAFANA_ADMIN_PASSWORD` is a
secret and must not be copied into documentation, commits, tickets, or command
history. For non-live work, retain `STARLINK_MODE=simulation`.

## Select an Immutable Release and Rollback Target

Before an authorized non-live update:

1. Select a reviewed immutable SHA-derived or versioned release tag.
2. Record the current immutable tag and the intended replacement in the approved
   change record. The current tag is the rollback selection.
3. Verify that the selected GHCR images correspond to the reviewed source
   revision and include the backend, Mission Planner, Prometheus, and Grafana
   images.
4. Verify the Git-stack template uses the four required host-path keys, the
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
   four required host-path keys in Portainer.
3. Enable image pulling so Portainer obtains the chosen immutable images.
4. Leave image pruning disabled. Pull without prune preserves the prior image
   selection for rollback.
5. Review the rendered template before submitting it. It must use GHCR images,
   baked monitoring configuration, the external `proxy` network, and the four
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
http://grafana:3000/api/health
http://mission-planner/
http://mission-planner/api/v2/missions
```

The first three probes verify backend health, Prometheus readiness, and Grafana
health. The final two verify the Mission Planner dashboard route and its
same-origin API behavior. Record only pass/fail results and the immutable image
selection; never include environment addresses, paths, credentials, or storage
identifiers in the repository.

## Rollback

If an authorized non-live update fails, set `STARLINK_IMAGE_TAG` back to the
recorded prior immutable selection and use the same Git-stack update flow:

- keep image pulling enabled so the known-good selection can be retrieved
- keep image pruning disabled so rollback images remain available
- preserve all four persistence categories and their existing host paths
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
- confirmation that all four host-path categories were supplied and retained
- non-live probe pass/fail outcomes
- confirmation that external-proxy aliases and Mission Planner same-origin
  behavior were preserved
- Brian's explicit live approval, if a separate live rollout is authorized

For repository-managed local development, use the
[Setup guide](../setup/README.md) instead. This runbook applies only to the
dedicated Portainer GHCR template.
