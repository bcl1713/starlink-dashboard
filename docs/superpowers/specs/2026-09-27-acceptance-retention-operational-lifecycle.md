# Acceptance Retention Operational Lifecycle Controls

This companion specifies the runner Docker/workspace, GitHub Actions build-record,
and GHCR package controls required by the
[Retention Design](2026-09-27-acceptance-evidence-retention-design.md).
It does not change that design's fixed three-generation policy, protected-final
authority, no-follow requirements, or legacy-material protections.

## Runner-owned Docker and workspace lifecycle

The final-lane wrapper creates each Buildx builder, build cache, workspace, and
acceptance image with an explicit ownership label containing the lane, exact SHA,
and task identifier. It uses a task-owned builder rather than Docker's shared
default builder. At normal lane cleanup, it removes the task-owned builder and
verifies that its task-owned cache is absent. It never calls broad `docker builder
prune`, `docker image prune`, `docker system prune`, or an unscoped cache-removal
command.

After choosing the retained three completed candidate generations, retention may
remove only an image or workspace that has a regular ownership marker or all
required ownership labels, belongs to an eligible generation, has no container
references, is not referenced by the protected ledger, and passes root-containment
and liveness checks. Existing unlabelled acceptance images, shared BuildKit cache,
and unmarked workspaces are legacy material: inventory and anomaly report only.

Acceptance volumes remain inventory-only and are never removed automatically.
The runner reports their names, labels, sizes, and eligible-generation association
because the standing volume-retention policy preserves them. If their aggregate
size becomes material, volume removal requires a separate explicit authorization
and design; the retention command must not infer that permission from image or
workspace cleanup.

Stale Git worktree registrations for a removed, marked runner-owned checkout are
pruned only after the checkout absence and marker association are verified. The
command never runs a broad worktree cleanup over user-owned branches or unmarked
historical registrations.

## GitHub Actions build-record lifecycle

The GHCR publishing workflow retains build records for only three publish
generations: the current run plus the two newest prior completed publish runs. A
post-publish retention job, after every matrix image build succeeds, identifies
artifacts created by older completed runs of this exact workflow on `dev`, reports
the protected run identifiers, and deletes only their `.dockerbuild` artifacts
through the GitHub Actions API. It uses explicit `actions: write` permission,
never deletes artifacts from another workflow, tag, branch, or in-progress run,
and fails closed on pagination, workflow identity, or artifact ownership
ambiguity.

The workflow contract checker verifies the retention job, its dependency on the
successful publish matrix, fixed count of three completed generations, API scope,
and no broad artifact deletion. Tests use API fixtures for run/artifact selection
and refusal paths. A failed artifact-retention job must not retroactively claim
the image publish failed, but it must be visible as a distinct workflow failure
requiring maintenance investigation.

## GHCR package inventory

Every `dev` publish creates immutable `sha-<40-hex>` package versions for four
images. The repository cannot determine whether an older SHA tag is currently
deployed through an externally supplied `STARLINK_IMAGE_TAG`. Therefore GHCR
retention is report-only until a deployment inventory establishes authoritative
protected tags.

The post-publish retention job reports package versions beyond the newest three
SHA-only generations per image, all non-SHA tags, and any package/API anomaly. It
does not delete a GHCR package version, retag an image, or infer active deployment
state from repository files. A future deletion design requires an independently
verified deployment inventory and a new approved specification.

## Verification additions

In addition to the main specification's tests, cover:

- task-owned Buildx builder/cache cleanup, eligible labelled-image/workspace
  deletion, protected-ledger refusal, and no broad Docker-prune invocation;
- fixed-count GitHub Actions build-record selection/deletion, pagination and
  foreign-workflow refusal; and
- GHCR report-only package inventory, including non-SHA tag preservation and API
  anomaly reporting.

Update the acceptance-platform operations guide and external-host final acceptance
runbook with runner-owned Docker/workspace lifecycle, Actions build-record cleanup,
GHCR report-only inventory, recovery behavior, and the prohibition on volume,
profile, user-owned repository, or unclassified legacy deletion.
