# Stage 5 offline qualification plan

**Goal:** qualify the diagnostic pipeline at the Stage 4 delivery without
running application infrastructure.

**Spec:** PR #408 orchestrator checkpoint 6353772496 and this session's Stage 5
requirements.

**Architecture:** retain exact guarded A/C exports and pinned #407 dependency.
Feed deterministic Stage 2 probe events and fake-Page Stage 3A records into the
real owner, evidence sink, collector and analyzers. Independently verify reports
and artifacts. Changes are confined to the diagnostic integration package and
this plan.

- [ ] Reproduce exact sources and dependency inventories; preserve all
      production and frozen bytes.
- [ ] Run the existing bounded Python/Node baseline; independently review Stage
      4's ten fixes.
- [ ] Add persisted deterministic end-to-end fixtures, positive and negative
      qualification, actual offline CLI replay and independent verification.
      Repair reproduced integration-only defects with failing regressions first.
- [ ] Run relevant Python, fake-Page Node, frontend and static checks; record
      coverage and uncovered runtime risks.
- [ ] Publish immutable hashes, review dispositions, boundary matrix, future
      Forge preflight/runbook and verified cleanup to draft #408; stop.

Constraints: no images, browser launches, services, application HTTP traffic,
packet capture, calibration or sustained tests; no production/frozen
collector/harness changes; no privileges or Nginx/network changes. Stage 3B
deferred. Observer cadence requirement remains 1.5 seconds. PRs remain
draft/unmerged and issues open.

Ruling: base the isolated task branch on the explicitly requested Stage 4
commit, which descends from origin/dev; fast-forward the existing #408 head
after verification. Preserve other open-PR worktrees.

Review focus: complete-summary/loss gates, corrupted sequence/source/clock
identity, missing/duplicate events, restarts, partial body/snapshot references,
unsupported paint/wire and cleanup failures. Runtime behavior remains
unqualified.
