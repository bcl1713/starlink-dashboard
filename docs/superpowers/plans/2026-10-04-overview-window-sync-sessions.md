# Issue 257 display-session delivery record

Supplement to the
[tracked progress](2026-10-04-overview-window-sync-progress.md) and
[approved plan](2026-10-04-overview-window-sync.md). Read alongside them.

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
  high-water marks prevent regressive data from renewing peers, including after
  departure/expiry. Controller requests require a live target/capability; the
  host checks its current capabilities again before invoking the callback.
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
  `services-first.log`. Additional behavioral RED: **4 failed / 78 passed** for
  inherited/accessor/extra capability fields and subscriber notification during
  failed departure; `edge-red.log`. GREEN: **2 files / 82 tests**;
  `edge-green.log`.
- UUID fallback RED: **1 failed / 27 passed**, `uuid-red.log`, when
  `crypto.randomUUID` is unavailable. GREEN: **2 files / 83 tests**,
  `uuid-green.log`, including unique session/request UUIDs and accepted
  delivery.
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
  markdownlint and whitespace checks passed; `static.log`, `docs-lint.log`. No
  new dependency, lockfile, REST polling, chart/form, camera, UI or
  browser-fixture changes.
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
  entry and evidence reference. The central progress table remains
  authoritative. Cost if wrong: successor sessions must follow this additional
  local link.
- Next: controls-plan **Task 4: Deliver Configuration controls and honest
  fullscreen feedback** only. Verify exact SHA/branch/status/remote and read
  design/main plan/handoff/progress/controls plan. Do not repeat baseline, Tasks
  1–3 or approval gates. Carry all prior rulings and fixture contracts.
  Commit/push Task 4 implementation/checklists/progress when verification passes
  and stop with Task 5 handoff (same task if incomplete). Continue the session
  chain through Task 5, independent review and PR/merge under inherited
  authorization; preserve all shared work/evidence, protection and required
  acceptance/exact-head checks. No force-push, deploy, main promotion or shared
  resource deletion.

## Task 4 — Configuration controls (complete)

- Starting SHA: `badd556b47fa5e81768ccc479d70b918a82a84fb`; verified clean
  `/tmp/starlink-257`, correct feature branch and exact matching pushed SHA.
  Remote `dev` remains `b2ea3341f78137c1409a618c8d8da5814a14dac2`; no feature PR
  exists. Original checkout, other worktrees and all prior evidence preserved.
  Carry reconciliation before final acceptance without force-pushing.
- Added the approved host/controller hooks, shared fullscreen helper and
  Configuration display card. Existing Task 3 protocol/session interfaces and
  services are unchanged. The host reads the latest committed reset callback,
  checks deadlines before invocation and after native completion, publishes
  actual document state, and releases its effect-owned session on unmount.
- Recenter acceptance describes reset callback execution, not a settled camera
  animation. Configuration retains its foreground window; commands target only
  its selected Overview. A second peer invalidates automatic selection;
  selected-peer loss requires explicit choice even when one peer remains.
- Open Overview calls `window.open('/overview', '_blank', 'noopener')` directly
  on click. A newly discovered peer confirms connection; null handles do not
  imply popup failure. Three seconds without a new peer gives popup guidance.
- Local trusted clicks invoke the shared helper before its first await. Missing
  API/rejection/fulfillment without actual root entry never claims fullscreen.
  Actual fullscreen entry clears obsolete local rejection and controller
  guidance; local exit publishes Windowed. Exact fallback:
  `Click Fullscreen in the Overview window to finish.`
- Added accessible status/alert feedback and native keyboard controls. Overview
  labels match selector labels; labels and fullscreen feedback occupy the
  existing responsive controls grid. Camera/Canvas/chart/draft and REST refresh
  ownership are unchanged. No settings or caches enter the command channel.
- In-flight deadline unit regression proves retained controller timeout, no late
  host success feedback, no replay/new expired invocation, and authoritative
  actual fullscreen presence. Native fullscreen has no abort API; timeout does
  not cancel an already-issued request.
- Environment-local evidence:
  `/tmp/starlink-257/.superpowers/sdd/2026-10-04-overview-window-sync-controls/evidence/task4/`.
  Tracked counts/rulings here survive branch transfer; traces/screenshots/logs
  and `self-review.md` are local. Fixtures are not real-backend acceptance.
- RED: four missing-module suites (`ui-red.log`); existing fullscreen control
  **3 failed / 2 passed** (`local-red.log`); browser **4 failed** on absent
  identity/control UI (`browser-feature-red.log`). Normal browser RED build
  initially stopped because new tests imported intentionally absent modules.
- Ruling: use an evidence-local Vite dev-server config for browser RED only —
  expose absent UI without changing tracked runtime config. Every GREEN browser
  run uses the normal production build/preview. Cost if wrong: development RED
  alone proves no production behavior; final production checks remain required.
- Debugging corrected an unbound static flush in the test transport and removed
  Playwright-only `exact` options from Testing Library calls. Initial
  integration **6 files / 40 tests passed**. Self-check regressions then
  demonstrated stale fallback after actual entry (**1 failed / 13 passed → 14
  passed**) and retained host rejection hiding repeated requests after exit (**1
  failed / 5 passed → 6 passed**). Logs: `actual-state-{red,green}.log` and
  `repeat-feedback-{red,green}.log`.
- Ruling: allow 90s for two-display recenter browser cases — two WebGL starts
  plus prescribed 15s peer expiry exceeded the default 60s total budget. Command
  deadline remains 3s; peer-loss assertion remains 20s. Cost if wrong: slower
  overall failure; no relaxed command or expiry contract.
- Ruling: probe native activation/state through CDP with `userGesture: false` —
  Playwright `page.evaluate` grants synthetic activation and invalidated the
  initial remote rejection test. Cost if wrong: probe is Chromium-specific,
  matching the browser project. `browser-first.log`, `browser-second.log` and
  `native-third.log` preserve the failed test preconditions/locator diagnosis.
- Ruling: portable headless tests use native API exit; optional
  `OVERVIEW_NATIVE_ESCAPE=1` headed Xvfb tests send actual OS Escape with XTest
  — CDP Escape did not exercise native browser exit in headless or headed runs.
  Cost if wrong: extra OS evidence requires isolated X11, Python 3 and libXtst;
  no application dependency or fullscreen permission changes. Logs:
  `native-fourth.log`, `native-headed.log`, `native-os.log`.
- Actual native OS lane: **1 passed (22.8s)**. Real remote rejection with no
  activation, trusted local native entry, already-fullscreen acknowledgment,
  Configuration foreground on remote request, OS Escape and reported Windowed
  state passed. No permission bypass or altered browser launch policy.
- Final `./tools/verify frontend`: **89 files / 776 tests passed**, production
  TypeScript/Vite build passed; `frontend-final.log`. Existing large-chunk
  advisory remains. Changed-file ESLint/Prettier passed: `static-final.log`,
  `prettier-final.log`.
- Author self-check used the code-review checklist; two material feedback
  findings have RED-to-GREEN fixes. This is not independent whole-branch review.
- Runtime: Node **22.22.2**, npm **10.9.7**, carried runtime PATH. No installs,
  dependencies/lockfile changes or Docker operations. Actor endpoint/context,
  proxy and CA preserved; cloud status capability/policy snapshot unavailable.
  Preview/Chromium and remote checks required sandbox escalation; authorized
  isolated checks succeeded. No shared-resource cleanup.
- Final controls browser command (frontend):

  ```sh
  PLAYWRIGHT_PORT=5278 npx playwright test \
    tests/e2e/overview-window-controls.spec.ts --workers=1
  ```

  **4 passed (2.3m)**; `browser-final.log`, traces/screenshots under
  `browser-final/`. Targeted recenter restores the selected camera without
  changing the other display, navigation, Canvas/plots or retained history.
  Native fullscreen remains active. Closing the selected display disables
  commands without retargeting.

- Focused existing layout regressions: responsive long-content rotation and
  fullscreen scene/history round trip: **2 passed (28.5s)**; `layout-final.log`
  and `layout-final/`. These are focused Task 4 checks, not Task 5's full lane.
- Changed documentation markdownlint, filename and whitespace checks passed.
  Preview port 5278 and isolated Xvfb runs released; no Docker resources created
  or removed. No material Task 4 defects left after the author self-check.
- Commit: `feat(configuration): control selected Overview displays`, including
  implementation/checklists/progress. Exact ending SHA, normal push/remote
  check, fresh post-commit task-done output and full Task 5 message are saved at
  local `task5-handoff.txt` beside evidence and emitted at completion.
- Next: acceptance-plan **Task 5: Real-request acceptance, regressions, and
  operator guidance**, steps 1–6 only. Task 5 step 7 is the separate independent
  review session. Read all approved plans/design/protocol and both progress
  records; verify exact SHA/branch/clean status/remote before edits. Carry all
  prior rulings and fixture contracts, including route radius/eight segments and
  post-startup navigation baseline plus Canvas/uPlot identity.
- Current-dev reconciliation before final acceptance, real Nginx/backend
  evidence, full regression gates, independent review, required exact-head CI
  and feature PR/merge remain pending. Issue readiness is not claimed. Inherited
  authorization continues through PR/review fixes/dev merge after gates pass; no
  force-push, protection bypass, deployment, main promotion or shared deletion.
