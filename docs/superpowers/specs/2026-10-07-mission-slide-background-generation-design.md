# Draft mission slide background generation design

Generate slides after a leg is created or a saved change affects its output.
When a newer change arrives, interrupt obsolete generation and restart from the
latest committed inputs. Ready mission exports assemble current slide artifacts
instead of building timelines, rendering maps, or generating slides on demand.

This is phase two of the parallel customer briefing trial. The first phase
validates the new presentation alongside the existing deck. This follow-up
changes generation timing for both decks without changing legacy slide content
or replacing the established export. It is a design for review, not code.

## User flow

A successful leg save returns promptly after committing mission data and
recording a generation request. It does not wait for rendering. Show a concise
slide status near the export action: Preparing slides, Ready, or Needs retry.
A second save supersedes unfinished work for that leg automatically.

When all required artifacts are current, Export assembles the normal ZIP and
both mission decks from cached per-leg content. The customer performs the same
export action and does not manage workers, revisions, or artifact files.

If required legacy slides are not ready, Export starts asynchronous preparation
and shows progress rather than serving stale slides or running heavy work in the
request. The download becomes available when the current artifacts are ready.
If the mission changes while preparation is pending, restart preparation against
the latest saved snapshot and update progress. Unsaved edits are not exported.

If legacy generation fails, explain which leg needs retry and keep other ready
artifacts. Retry queues background work. If only the trial deck fails, deliver
the established export with a concise trial warning, matching phase one's
failure isolation. Do not silently use slides from an older saved revision.

## Existing context and integration

Mission persistence is file-based in `app/mission/storage.py`, with mission
locks. Mutation routes are in `app/mission/routes_v2.py`; export assembly is in
`app/mission/package/__main__.py`. Existing background tasks serve other
purposes and do not establish a durable, latest-change-wins slide job system.

Use the same timeline snapshot and slide builders as the trial design. Separate
generation scheduling, artifact publication, and export assembly so changing
when slides are built does not change their expected content.

## Generation triggers and dependencies

Queue work only after successful persistence for leg creation, saved changes,
imports, and duplication. Leg edits include departure adjustments, route
selection or geometry, transport settings, outages, AR tracks and overrides,
advisories, and notes that appear in slides. Failed validation and unsaved UI
edits do not trigger generation.

Track dependency changes as well as leg edits: referenced route timing and
geometry, POIs, applicable satellite or coverage configuration, mission
metadata, and renderer/template/brand-asset versions. Invalidate affected legs
when those inputs change. Persist reverse dependency references or reconcile
them against committed data; do not rely only on a leg's updated timestamp.

Reordering or adding/removing legs invalidates the mission composition and any
leg artifact with order-dependent content. Keep Leg N of M headers as assembly
fields where possible so ordering alone does not rerender maps. Deletion
cancels that leg's work and prevents a late result from recreating its cache.

## Durable scheduling and restart behavior

Persist desired generation state in a dedicated slide-cache store, separate
from mission import/export data. A request records leg identity, input
fingerprint, immutable input snapshot, generation token, and state. States are
queued, running, ready, failed, superseded, or deleted. Persist safe error
summaries separately from worker diagnostics.

Use atomic writes and per-leg locking for request updates. Enqueue idempotently:
the same desired fingerprint reuses ready artifacts or existing work. A newer
fingerprint replaces queued work and requests cancellation of running work for
that leg. Coalesce rapid saves briefly without making save responses wait.

A single durable coordinator initially dispatches one active generation process
at a time; concurrency is configurable after measurements. Multiple API
processes do not each start duplicate coordinators. Claim work with an exclusive
lease and renew it while running. Startup recovery reconciles committed inputs
with desired fingerprints, repairs missed post-save requests, and requeues
expired running leases. Browser sessions do not own job lifetime.

Run heavy timeline, map, and deck work in a cancellable child process. New saves
request cooperative cancellation, then terminate and reap only that obsolete
job's process group and browser descendants after a bounded grace period.
Do not leave stale work consuming the worker slot. Requeue only the newest
desired generation. Cancellation of one leg must not interrupt another leg.

Use explicit job time limits and clean up temporary outputs and owned processes
on success, failure, cancellation, and service restart. Render time limits and
map fallback rules remain those of the trial design. Bound retries for transient
errors; repeated failure exposes Needs retry rather than an infinite retry loop.
Persisted requests and artifacts survive application restart.

## Artifact identity and atomic publication

Fingerprint all effective inputs that affect slide content: committed leg and
parent metadata, resolved route and departure, availability and restriction
inputs, dependency versions, rendering configuration, and deck template version.
Exclude volatile bookkeeping timestamps that do not affect content.

Generate legacy and trial per-leg slide content, maps, and a provenance manifest
in a job-owned staging directory. The manifest records the input fingerprint,
generation token, source revisions, template versions, deck status, and warnings.
Validate completed PowerPoint files before publication.

Before publishing, acquire the per-leg lock and compare the job token and
fingerprint to the current desired record. Publish by atomic promotion only if
both still match and the leg still exists. A cancelled job that finishes late
cannot replace newer artifacts. Readers never see partially written files.
A trial-only failure can publish valid legacy content with a failed trial status.

Store assembly-ready PowerPoint fragments with their embedded assets and slide
relationships. Mission titles, leg index, ordering, and headers are filled during
composition. Composition must preserve editable text, images, relationships,
and styles; simple ZIP concatenation of PowerPoint files is not sufficient.

Retain the current ready artifact and one previous ready artifact for diagnosis,
plus artifacts leased by an active export. Previous revisions are never default
export candidates. Remove superseded staging outputs promptly; bound abandoned
export leases and clean up deleted-leg artifacts. Garbage collection must not
remove files being read by an active export.

## Assembly and consistency

An export captures the latest committed mission snapshot and expected
fingerprints for every ordered leg. Assemble only matching ready artifacts,
using read leases so replacement or cleanup cannot remove files mid-assembly.
The ready path performs no timeline rebuild, map rendering, or slide generation.

A later save does not mutate an export already assembling from a fully ready
snapshot. Pending preparation follows the latest saved mission instead, with
clear progress. Each delivered package has one internally consistent snapshot
and provenance; never mix old and new revisions across decks or legs.

Trial enabled means include the trial deck when all required trial fragments
are ready. If a trial fragment has failed, deliver the legacy package with the
trial warning; do not claim that a partial trial is complete. Changing the
feature flag affects inclusion, not legacy artifacts or mission data.

First use, deployment/template upgrades, and recovered missing cache entries
queue background backfill. They may show preparation progress, but must never
fall back to synchronous heavy generation on the ready export path.

This phase caches slide artifacts. CSVs, mission JSON, route files, and POIs
continue to use the existing export pipeline. Measure their assembly cost rather
than claiming all export processing has disappeared.

## Verification and responsiveness

Verify the following with deterministic fixtures and production-path controls:

1. Creation and successful saves enqueue work promptly; failed saves and
   unsaved edits do not. Duplicate requests do not duplicate generation.
2. A save during rendering cancels and reaps the obsolete job, runs the latest
   revision, and cannot publish an older result afterward.
3. Deletion during work prevents resurrection; changes to referenced routes,
   restrictions, parent metadata, and templates invalidate the correct outputs.
4. Restart recovers queued and interrupted work; multiple API processes and
   expired leases cannot publish competing results.
5. Ready export assembles both decks without calling timeline builders,
   renderers, or slide generators; each leg and deck matches one snapshot.
6. Missing artifacts show preparation, failed legacy work shows retry, and
   trial-only failure preserves the established package with a warning.
7. Cache publication is atomic. Export leases protect files during concurrent
   replacement and cleanup; pending exports follow changes without mixing data.
8. Composed decks open offline and preserve legacy content, trial layout,
   embedded assets, editable objects, and correct Leg N of M headers.
9. Jobs respect resource limits and leave no child processes or staging files
   after cancellation, timeout, or shutdown; unrelated jobs keep running.

Measure save-response latency, cancellation-to-restart delay, generation time,
and ready-export latency on identical small, large, and multi-leg fixtures.
Compare the ready path with the existing export-time generation baseline and
report the remaining assembly cost. The acceptance condition is that save
responses do not wait for generation and ready exports contain no heavy slide
generation, with a measured improvement in responsiveness.
