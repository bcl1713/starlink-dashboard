# Issue 257 display-session delivery record

Supplement to the [tracked progress](2026-10-04-overview-window-sync-progress.md)
and [approved plan](2026-10-04-overview-window-sync.md). Read alongside them.

## Task 3 — validated presence and targeted sessions (complete)

- Starting SHA: `5c9ef5a1d03eccda22efac6017ebcc9a26f8f7dc`; branch
  `feat/257-overview-window-sync`, clean `/tmp/starlink-257` and matching pushed
  feature SHA verified before edits. GitHub issue 257 remains open; PR 258 is
  merged/included; no feature PR exists. Remote `dev` remains
  `b2ea3341f78137c1409a618c8d8da5814a14dac2`. Carry the Task 2 ruling to
  reconcile before final acceptance without force-pushing and rerun affected
  verification. Original checkout's separate acceptance-plan work and other
  worktrees are preserved.
- Added only the two service modules and their unit tests. Exported
  `DisplayAction`, `DisplayResult`, `DisplayPeer`, `CommandFeedback`,
  `DisplaySnapshot`, `OverviewDisplayMessage`, `parseOverviewDisplayMessage`,
  `DisplaySessionOptions`, `OverviewDisplaySession`, and
  `createOverviewDisplaySession` with the approved interfaces. These services
  are not yet wired into React; Task 4 owns that integration.
- Protocol validates exact own data fields, IDs/labels up to 128 characters,
  positive safe sequence integers, finite nonnegative expiry, booleans and
  closed action/result values. Capability arrays are dense, contain no
  inherited/accessor/extra fields and have no duplicate actions. Parsed values
  are detached from caller-owned data. No settings/cache payloads or executable
  commands are accepted.
- Session uses `starlink-overview-display-v1`, UUID IDs and matching
  `Overview <final-six-characters>` labels. Immediate discovery/presence,
  targeted discovery replies, one 1000ms scheduler per session, five-second
  presence and fifteen-second receive-time peer expiry. Presence/bye sequence
  high-water marks prevent regressive data from renewing peers, including
  after departure/expiry. Controller requests require a live target/capability;
  the host checks its current capabilities again before invoking the callback.
- Three-second commands reach only the selected host, which retains 128
  `(sender, requestId)` pairs in FIFO order, including pending callbacks.
  Duplicates may replay cached results but never execute again within that
  bounded window. Wrong target/peer/action/request, duplicate and late results
  cannot replace current feedback. Results use actual host fullscreen state;
  independent presence remains authoritative after timeout.
- Ruling: a callback resolving at/after its command deadline yields `expired`
  rather than a late success; the controller retains timeout — implements the
  carried native-fullscreen limitation without pretending to abort the browser
  operation. Cost if wrong: a completed action can be visible only through
  subsequent actual-state presence, rather than a late success message.
- Ruling: `close()` sends departure best effort and never notifies a disposed
  subscriber, even if posting fails — required for Task 4 effect/StrictMode
  cleanup. Transport failures while active instead emit `available: false`,
  clear peers, settle pending feedback unavailable and release resources. Cost
  if wrong: consumers must use effect teardown as their lifecycle authority.
- Ordered in-memory transport tests use separate instances, asynchronous FIFO
  delivery and no self delivery. Cover zero/one/multiple controllers/displays,
  existing/new displays, five-second actual-state heartbeats, stale peers and
  decreasing sequences, targeted recenter, in-flight/completed duplicates,
  deadline delivery/completion, bounded FIFO, callback throws/rejections,
  missing/failed channels, messageerror, bye and idempotent cleanup returning
  listeners/timers to baseline. These unit fixtures are not browser or
  production acceptance.
- Environment-local evidence directory:
  `/tmp/starlink-257/.superpowers/sdd/2026-10-04-overview-window-sync-controls/evidence/task3/`.
  Supplemental ledger/brief are in this controls-plan workspace; refresh-plan
  Task 1–2 evidence remains preserved. Commands run at repo root with
  `npm --prefix frontend/mission-planner`, equivalent to the plan's frontend
  working directory.
- Prescribed RED: both new suites failed on missing modules before production
  code; `services-red.log`. Initial GREEN: **2 files / 78 tests**;
  `services-first.log`. Additional behavioral RED: **4 failed / 78 passed**
  for inherited/accessor/extra capability fields and subscriber notification
  during failed departure; `edge-red.log`. GREEN: **2 files / 82 tests**;
  `edge-green.log`.
- UUID fallback RED: **1 failed / 27 passed**, `uuid-red.log`, when
  `crypto.randomUUID` is unavailable. GREEN: **2 files / 83 tests**,
  `uuid-green.log`, including unique session/request UUIDs and accepted delivery.
- Ruling: use a version-4 UUID from `crypto.getRandomValues` when
  `crypto.randomUUID` is unavailable — retain the UUID identity contract on
  origins lacking that API, without dependencies or weak random identifiers.
  Cost if wrong: compatibility still requires the standard Web Crypto random
  primitive; broader obsolete-browser support is outside this task.
- Systematic debugging: the first full frontend gate passed **738 tests** but
  rejected the test channel constructor's parameter property under repository
  `erasableSyntaxOnly`; replaced it with a normal field/assignment.
  `frontend-first.log`, `build-red.log` and `build-green.log` retain evidence.
  The stricter capability parser subsequently exposed TypeScript's array mapped
  descriptor inference (`length` inferred as number); an explicit descriptor
  record annotation resolved the type error without changing validation.
- Final root `./tools/verify frontend`: **85 files / 743 tests passed**, and
  production TypeScript/Vite build passed; `frontend-final.log`. Existing
  chunk-size advisory retained. Changed-file ESLint/Prettier, changed-doc
  markdownlint and whitespace checks passed; `static.log`, `docs-lint.log`.
  No new dependency,
  lockfile, REST polling, chart/form, camera, UI or browser-fixture changes.
- Runtime remains Node **22.22.2** / npm **10.9.7**, using
  `/tmp/starlink-226-runtime/node-v22.22.2-linux-x64/bin`; final exact-head CI
  runtime verification remains required. No installs or Docker operations;
  inherited actor endpoint/context/proxy/CA configuration preserved. Cloud
  status tool/policy snapshot remain unavailable. Read-only remote verification
  required escalation after sandbox SSH/network denial; escalated checks passed
  using existing credentials/configuration.
- Commit: `feat(overview): add targeted display command sessions`, including
  implementation/checklists/progress. Exact ending SHA, normal push/remote
  verification, fresh post-commit task-done output and ready-to-paste Task 4
  message are recorded locally at `task4-handoff.txt` alongside this evidence
  and emitted at session completion, avoiding a self-referential tracked SHA.
- Task 3 unresolved: none. Tasks 4–5, current-dev reconciliation, real Nginx/
  backend acceptance, independent whole-branch review, exact-head required
  checks and feature PR/merge remain pending; issue readiness is not claimed.
- Ruling: keep this detailed entry in a linked session record because the
  repository limits documentation to 300 lines — preserve every prior progress
  entry and evidence reference. The central progress table remains authoritative.
  Cost if wrong: successor sessions must follow this additional local link.
- Next: controls-plan **Task 4: Deliver Configuration controls and honest
  fullscreen feedback** only. Verify exact SHA/branch/status/remote and read
  design/main plan/handoff/progress/controls plan. Do not repeat baseline,
  Tasks 1–3 or approval gates. Carry all prior rulings and fixture contracts.
  Commit/push Task 4 implementation/checklists/progress when verification passes
  and stop with Task 5 handoff (same task if incomplete). Continue the session
  chain through Task 5, independent review and PR/merge under inherited
  authorization; preserve all shared work/evidence, protection and required
  acceptance/exact-head checks. No force-push, deploy, main promotion or shared
  resource deletion.
