# Portainer GHCR Deployment Runbook

This runbook defines the supported deployment contract for the committed
Portainer/GitHub Container Registry (GHCR) profile tracked by
[issue #121](https://github.com/bcl1713/starlink-dashboard/issues/121).

It is for an operator preparing a non-live stack update or a Brian-approved live
rollout. It does not authorize workers to operate the live environment.

## Safety Boundaries

Do not use this runbook to:

- edit, deploy, or redeploy Portainer endpoint `3` or stack `180`
- change external DNS or proxy routing
- delete or recreate live named volumes
- inspect, copy, or commit the live stack configuration or its secrets

The live rollout and public-hostname verification are a separate, explicit
Brian-approved gate described in [Live Release Gate](#live-release-gate).

## Deployment Profile Contract

The Portainer profile is a Git-managed Compose stack. It must meet the following
contract:

- Images come from GHCR; services use `image:` references rather than local
  `build:` contexts.
- Portainer owns all runtime configuration and secrets. Do not create, copy, or
  require a repository `.env` file for this profile.
- Simulation is the safe default: set `STARLINK_MODE=simulation` unless the
  Brian-approved live gate authorizes a different value.
- Every deployed image is selected by an immutable Git SHA or versioned release
  tag. Do not deploy a mutable tag such as `latest`.
- The Compose profile joins the pre-existing external Docker network named
  `proxy`; the deployment does not create, replace, or reconfigure that network.
- The Grafana image retains the exact Infinity datasource plugin pin
  `yesoreyeram/infinity-datasource@3.11.1`. The image build assertion verifies
  that invariant before an image is published.

The implementation pins compatible upstream Prometheus and Grafana versions or
image digests. Operators must not replace those image selections with upstream
`latest` references.

## Portainer-Supplied Configuration

Enter runtime values in the Portainer stack environment/configuration UI. They
belong to the Portainer environment, not to a checked-out `.env` file.

Use placeholder values in operator documentation and change tickets; never put
credentials or live values in the repository. The following is a configuration
shape, not a file to copy into the repository:

```yaml
# Values supplied by Portainer, not a repository .env file.
STARLINK_MODE: simulation
GRAFANA_ADMIN_PASSWORD: <PORTAINER_MANAGED_SECRET>
STARLINK_IMAGE_TAG: <IMMUTABLE_GIT_SHA_OR_RELEASE_TAG>
STARLINK_MISSIONS_VOLUME: <EXISTING_MISSIONS_VOLUME_NAME>
STARLINK_SATELLITES_VOLUME: <EXISTING_SATELLITES_VOLUME_NAME>
STARLINK_SAT_COVERAGE_VOLUME: <EXISTING_SAT_COVERAGE_VOLUME_NAME>
STARLINK_ROUTE_VOLUME: <EXISTING_ROUTE_VOLUME_NAME>
STARLINK_SIM_ROUTE_VOLUME: <EXISTING_SIM_ROUTE_VOLUME_NAME>
STARLINK_POI_VOLUME: <EXISTING_POI_VOLUME_NAME>
STARLINK_PROMETHEUS_VOLUME: <EXISTING_PROMETHEUS_VOLUME_NAME>
STARLINK_GRAFANA_VOLUME: <EXISTING_GRAFANA_VOLUME_NAME>
```

`STARLINK_IMAGE_TAG` is the exact variable used by the committed profile to
resolve both GHCR images. Each `STARLINK_*_VOLUME` value names the corresponding
pre-existing external Docker volume. Portainer must provide all eight volume
values; the profile does not create, replace, or delete any volume.

For example, image references and the external proxy network use placeholders of
this form:

```yaml
services:
  backend:
    image: ghcr.io/<OWNER>/<BACKEND_IMAGE>:<IMMUTABLE_TAG>

networks:
  proxy:
    external: true
```

Do not substitute an unreviewed branch name, `latest`, a local `build:` block,
or a private value into this example.

## Select a Release and Prepare Rollback

1. Choose the release's immutable SHA or versioned release tag from the
   published GHCR images.
2. Record the currently deployed immutable tag and the intended replacement in
   the approved change record. The recorded current tag is the rollback target.
3. Confirm the selected tag belongs to the reviewed `dev` commit or approved
   release and that the images publish OCI source and revision/release labels.
4. Confirm the Git-managed stack contains the deployment profile and retains the
   external `proxy` network declaration.
5. Confirm Portainer, not the repository, holds all environment values and
   secrets. Keep `STARLINK_MODE=simulation` for non-live use.

Do not proceed if the tag is mutable, the rollback target is unknown, or the
profile requires a repository `.env` file.

## Update a Git-Based Stack

For an authorized non-live stack, use Portainer's Git-based stack update flow:

1. Select the reviewed Git repository, deployment-profile path, and approved Git
   reference.
2. Set the stack's Portainer-managed configuration values, including
   `STARLINK_IMAGE_TAG` with the chosen immutable image tag and all eight
   `STARLINK_*_VOLUME` values for the existing external volumes.
3. Enable image pulling during the stack update so Portainer fetches the chosen
   GHCR images.
4. Leave image pruning disabled. Pruning can remove the prior immutable image
   needed for rollback.
5. Review the rendered Compose configuration before submitting the update. It
   must use GHCR images, include the external `proxy` network, and have no local
   `build:` entries or repository `.env` dependency. Mission Planner traffic
   must continue through the proxy's same-origin route; do not replace it with
   direct container or host-port routing.
6. Perform only the authorized non-live validation. Stop rather than attempting
   a live deployment or changing external routing.

These steps describe the intended operational profile; they do not grant
permission to operate endpoint `3` or stack `180`.

## Roll Back

If the authorized update fails, roll back by changing the Portainer-managed
image selection to the recorded prior immutable SHA or release tag, then use
that same Git-based stack update flow:

- keep image pulling enabled so the known-good image can be fetched
- keep image pruning disabled so rollback images remain available
- retain the existing external `proxy` network
- retain existing named volumes

Do not roll back by using `latest`, recreating the stack or volumes, or making
manual DNS/proxy changes.

## Live Release Gate

A production rollout occurs only after all of the following are true:

1. The implementation and this documentation have passed independent review and
   merged to `dev`.
2. Brian explicitly approves the live Portainer deployment.
3. Brian explicitly approves public-hostname checks for `starlink.hblucas.org`
   and `mission-planner.hblucas.org`.
4. The approved operator confirms the deployed image tag, runtime mode, health
   checks, and rollback target without exposing secrets.

Workers must stop at this gate. They must not deploy or redeploy Portainer stack
`180`, touch endpoint `3`, alter external DNS/proxy routing, or recreate live
volumes.

## Authorized Live Verification

Only the Brian-approved operator performs this verification after the live gate
has been approved. Use the approved environment's values in Portainer; the
placeholder URLs below must not be replaced with live values in this repository:

```bash
curl --fail <DASHBOARD_PUBLIC_URL>/health
curl --fail <PROMETHEUS_INTERNAL_URL>/-/ready
curl --fail <MISSION_PLANNER_PUBLIC_URL>/api/v2/missions
```

The approved operator also checks the public hostnames `starlink.hblucas.org`
and `mission-planner.hblucas.org` through their approved routes. Mission Planner
must remain reachable through the same-origin proxy route; do not expose a
direct backend route as a replacement.

## Operator Completion Record

Record the following in the approved change record without including secrets:

- Git reference and immutable image SHA or release tag selected
- previous immutable tag retained for rollback
- confirmation that image pulling was enabled and pruning was disabled
- confirmation that Portainer supplied `STARLINK_IMAGE_TAG` and all required
  external-volume configuration values
- confirmation that the external `proxy` network and live volumes were left
  unchanged
- Brian's live-deployment and public-hostname approval, when applicable

For local development using repository-managed configuration, use the
[Setup guide](../setup/README.md) instead. This runbook applies only to the
Portainer GHCR deployment profile.
