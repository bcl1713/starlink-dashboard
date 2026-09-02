# React Operations Overview Rebuild Roadmap

> **For a new session:** Read this file, the linked product contract, the
> current phase file, and `SESSION-HANDOFF.md` before acting. Use direct/manual
> orchestration; do not create Kanban work.

**Goal:** Rebuild PR #143 from current `dev` as a responsive, independently
refreshed React operations overview, then prove and document it in bounded
phases.

**Architecture:** FastAPI supplies same-origin, typed, bounded data. React owns
independent live, history, and overlay lanes and bounded local history. A native
1920x1080 fullscreen view is the primary layout target. Grafana remains an
operational fallback, not an implementation dependency or core acceptance
oracle.

**Repository:** `bcl1713/starlink-dashboard`

**Durable PR:** `https://github.com/bcl1713/starlink-dashboard/pull/143`

**Base / feature:** `dev` / `feature/react-operations-overview`

**Reset baseline:** `07593c69040ad447000bf526d6453ec5c6faacfa`

**Historical head:** `e649ce169cd5adcbdd83d6264290b30d5221599e`

**Expected archive:** `archive/pr-143-pre-simplification-e649ce1`

---

## Authority and precedence

This roadmap and its seven supporting files supersede the retired
`docs/plans/2026-08-29-react-operations-overview.md` plan and supporting
`docs/plans/react-operations-overview/` set. Those old files may exist only on
the historical head/archive; do not copy them into the rebuilt branch.

The old implementation is historical evidence, not a source to continue
incrementally. Phase 1 starts from the published Phase 0 docs-only head.
Selective ideas or code may be inspected on the archive and deliberately adopted
after review; never cherry-pick the archive wholesale.

When requirements conflict, precedence is: Brian's explicit instruction, this
master roadmap,
[the product contract](react-operations-overview-rebuild/00-product-contract.md),
the active phase file, then advisory path notes.

## Delivery model and branch policy

- One writer owns the feature branch/worktree at a time. Reviewers do not edit.
- Orchestration is direct through PR #143; no Kanban tasks or shadow PRs.
- Each phase runs in a fresh session. Stop after its immutable candidate and
  handoff; the next phase starts only after Oracle publishes/reviews the prior
  one as specified.
- Every implementation increment follows RED, GREEN, REFACTOR and a focused
  check before the phase-wide checks.
- Independent review is ordered: specification compliance first, then quality. A
  quality review cannot waive a spec failure.
- Every public PR handoff identifies base/head refs, exact SHA, changed paths,
  commands/results, docs impact, unresolved questions, and next action.
- Oracle alone archives the old remote head, resets/publishes the durable
  feature ref, requests independent reviews, and changes PR/GitHub state.
- Integration targets `dev`. A future `main` release remains Brian-gated.

## Product and retired contracts

The binding behavior is in the
[product contract](react-operations-overview-rebuild/00-product-contract.md). In
particular, `1/2/5/10/30/paused` are the exact choices, and `1s` is
unconditionally the default and fastest; Phase 1 implements/tests rather than
decides this. The exact native-fullscreen 1920x1080 one-screen inventory is
exactly four clocks, current-position map, top-five applicable POIs, latency
current plus five-minute min/average/max, current download/upload, GEP,
obstruction, packet-loss current/average/max, selected interval, and last
successful update or concise failure. Route/track/active-link/satellites/events/
radar and ancillary controls are optional salvage, never Phase 1/2 dependencies.

History bootstrap calls `/api/monitoring/history` once; detected gaps on resume/
reconnect and explicit manual reconciliation trigger repairs. Optional 30–60s
reconciliation needs runtime evidence. Backfill only seeds/repairs bounded
30-minute buffers and never current values. Retire these old core gates:

- one global `Promise.all` refresh transaction;
- an exact five-second history request cadence;
- a six-viewport responsive acceptance matrix;
- object-identity/mutation-ledger evidence as a release requirement;
- generated shadow Compose files as the required runtime method;
- Grafana parity or retirement as a core gate.

They may be useful diagnostics, but they cannot block this roadmap unless Brian
explicitly reinstates one. Grafana remains available as fallback, and React must
make no request to it.

Phase 3 is non-writing. It retains only bounded raw ten-second browser request
timings/results, console/page/first-party errors, dimensions/bounding boxes,
exactly one viewport screenshot, and concise logs when useful—never a task-owned
evidence repository, manifest, checksum, or certification.

## Phase sequence and hard boundaries

1. [Phase 0: contract reset](react-operations-overview-rebuild/01-phase-0-contract-reset.md)
   creates only this eight-file documentation set from current `dev`.
2. [Phase 1: live data](react-operations-overview-rebuild/02-phase-1-live-data.md)
   builds independent live-stat, history, and overlay lanes; optimizes the
   `/api/status` hot path; and uses bounded local ring buffers.
3. [Phase 2: fullscreen layout](react-operations-overview-rebuild/03-phase-2-fullscreen-layout.md)
   implements exact native 1920x1080 fullscreen with no document scroll.
4. [Phase 3: runtime acceptance](react-operations-overview-rebuild/04-phase-3-runtime-acceptance.md)
   independently reviews an exact head in real Nginx and simulation-stack
   Chromium, including ten seconds of request evidence.
5. [Phase 4: docs and integration](react-operations-overview-rebuild/05-phase-4-docs-and-integration.md)
   updates operator/user docs, receives independent docs review, and integrates
   to `dev`; release to `main` requires Brian.

No production implementation begins during Phase 0. No phase absorbs the next
phase's work merely because a session has time left. Such enthusiasm has ruined
clean evidence before.

## Common execution contract

Each phase file must be executed in bounded order:

1. Verify repository, branch, exact input SHA, and clean worktree.
2. Re-read this roadmap, the product contract, phase file, and handoff.
3. Inspect advisory paths before finalizing exact files or commands.
4. For code, write the narrow failing contract test and prove RED.
5. Implement minimally, prove GREEN, then refactor without broadening scope.
6. Run focused checks, then all phase-required checks.
7. Clean task-owned artifacts and prove only intended files changed.
8. Commit, pin the immutable SHA, and rerun commit-safe verification.
9. Obtain independent specification review, then independent quality review.
10. Stop and publish the exact public handoff; start the next phase in a new
    session only after its gate is satisfied.

## Progress and reporting contract

At session start, report phase, input SHA, branch, and intended boundaries. At
each material gate, report RED/GREEN evidence, deviations from advisory paths,
and any blocker. Do not report `done` from an uncommitted or dirty tree.

Use
[the handoff template](react-operations-overview-rebuild/SESSION-HANDOFF.md). A
handoff output is complete only when it records:

- exact input and output SHAs without invented future values;
- every changed path and whether documentation changed;
- focused/full commands with exit status and useful counts;
- specification and quality reviewer identities/dispositions;
- cleanup evidence, unresolved questions, and explicit stop/next action.

## Documentation impact by phase

- Phase 0: adds only this executable roadmap; no user/operator behavior changes.
- Phases 1–3: update these plan/handoff records only when the contract changes;
  user/operator docs remain pending and are called out honestly.
- Phase 4: updates operator, user, architecture, and rollout/rollback material
  as required by the shipped behavior.

## Final responsibility map

| Responsibility                   | Owner                                  |
| -------------------------------- | -------------------------------------- |
| Product decisions and main gate  | Brian                                  |
| Remote archive/reset/publication | Oracle                                 |
| Active phase implementation      | One designated writer                  |
| Specification review             | Independent reviewer, no branch edits  |
| Quality review                   | Different independent pass after spec  |
| Runtime/browser acceptance       | Independent Phase 3 acceptance session |
| `dev` integration                | Oracle after Phase 4 gates             |
| `main` release                   | Brian, explicitly                      |

## Roadmap completion

The roadmap is complete only when Phase 4 is integrated into `dev`, all public
handoffs point to immutable reviewed SHAs, and Brian has been given the separate
choice to release to `main`. Phase 0 completion alone authorizes only archive
and docs-only branch publication by Oracle; it authorizes no production work in
this session.
