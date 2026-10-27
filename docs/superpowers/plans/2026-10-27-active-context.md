# Active mission context implementation plan

> Execute inline with test-driven development. The requested specification is
> GitHub issue #392.

**Goal:** Remove repeated retained-mission parsing and selected-mission
admission reads from live telemetry ticks while preserving durable mission
truth.

**Architecture:** Cache an immutable serialized active selection, mission
digest, and route revision under the existing repository gate. Local mission
mutations advance a generation independently of metrics subscribers. A periodic
filesystem inventory reconciles external edits (including membership, leg files
and pending journals); unchanged inventories require no JSON reads. A
lifespan-owned serial reconciler runs filesystem work on an executor, separately
from live ticks, and is drained during shutdown. Manual ticks without a lifespan
owner reconcile on their existing worker. There is no filesystem watcher. Public
consumers receive detached mission/leg models; live recording uses a compact
immutable identity binding. Route identity is checked at every admission.

**Constraints:** Preserve current public response models, activation/conflict
checks, replay/simulation behavior, and repository-first lock order. External
edits are checked once per second plus up to 250ms scheduling delay while live;
failed reconciliation must discard the previous context. No new dependency. The
lifespan reconciler must drain its executor work during shutdown. No merge or
rollout.

## Tasks

- [x] Add regression coverage counting real JSON reads, directory enumerations
      and stat work across 100+ stable resolutions; test local saves/switches,
      external edit/removal, duplicate IDs, corrupt files, route replacement,
      and recovery.
- [x] Implement cache and bounded reconciliation; serialize only the selected
      mission, retain a meaningful generation, and rate-limit unavailable
      logging to state transitions. Reuse existing persistence invalidations and
      cover direct deletion.
- [x] Replace live admission's selected-mission reload with snapshot validation.
      Test live binding, source changes during recording,
      replay/simulation/no-mission paths, and locking.
- [x] Benchmark 0/1/10/100 missions with
      filesystem/read/byte/validation/log/time counters. Run scoped and broader
      regressions, lint, production-path acceptance and a matched 60-minute
      live-like soak where runtime permits. Record unavailable coverage
      explicitly.
- [x] Review, commit, push and create a PR targeting dev. Verify no task-owned
      runtime resources remain; retain the open-PR worktree and evidence.

## Review focus

External mutation while reading must not publish a mixed generation. Duplicate
IDs must not hide conflicting active legs. Local invalidation must work without
a metrics subscriber. Mutable API projections must not poison cached truth. A
mutation between telemetry capture and publication must reject the old mission
binding.
