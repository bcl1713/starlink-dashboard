# Overview Window Synchronization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if the user
> selects delegation. Execute the checkbox steps in the linked task plans in
> order. The approved session-by-session handoff protocol below takes priority
> over skill defaults that continue through every task in one session.

**Goal:** Automatically apply saved Configuration/Missions changes to existing
Overview windows and expose acknowledged display controls on Configuration.

**Architecture:** Overview opts into background refresh through its existing
React Query observers; REST responses remain the saved-state authority. A
versioned BroadcastChannel provides ephemeral presence and targeted display
commands. The mounted globe, charts, local drafts, and existing data contracts
retain their ownership.

**Tech Stack:** React 19, TypeScript, TanStack Query 5, BroadcastChannel,
Vitest/jsdom, Playwright Chromium, production Nginx/FastAPI, Docker Compose.

**Spec:** [Approved design](../specs/2026-10-04-overview-window-sync-design.md).

**Status:** Approved by the user on 2026-10-04. Execution method: one new
session per task, followed by separate fresh-review and PR/merge sessions. Tasks
1–4 and Task 5 steps 1–6 are delivered; independent review is complete with
[R1 Important open and R2 Minor](2026-10-04-overview-window-sync-review.md).
Integration and fresh follow-up review remain pending. See the progress record.

## Global Constraints

- Saved-state polling: five seconds; no Overview focus change required.
- Controlled browser propagation ceiling: eight seconds after successful save.
- Heartbeat: five seconds; peer removal: fifteen seconds without heartbeat.
- Command deadline: three seconds; no execution of expired delivered commands.
- Settings/mission state comes from successful REST responses, never channel
  payloads, unsaved drafts, or optimistic cross-window writes.
- Keep one polling owner per query and the existing live-data cadence. No
  additional server push infrastructure or new production dependencies.
- Maintain native fullscreen, manually explored camera intent, mounted Canvas
  and charts, retained history, honest gaps, and existing freshness semantics.
- Multiple displays require explicit target selection; disappearing targets do
  not cause silent retargeting.
- Fullscreen state comes from the target document; rejection offers the local
  Fullscreen control. No special browser permissions or launch flags required.
- Browser/OS suspension catches up on resumption rather than promising an
  impossible wall-clock bound.
- Keep Docker's inherited DOCKER_HOST/context and proxy/CA trust. Acceptance
  uses isolated names, volumes, and loopback ports; no shared installation data.
- The user authorizes a feature-branch PR and merge into `dev` after applicable
  acceptance, independent review, and exact-head required checks pass. No `main`
  promotion, deployment, or changes to unrelated open issues are authorized.

## Review Focus

1. An unfocused Overview must receive saved labels/timezones without resetting
   the operator's camera or an unsaved Configuration form (refresh Task 1).
2. A slow pre-save read, failed save, or window-size mismatch must not overwrite
   newer confirmed local settings or mislabel cached history (refresh Task 2).
3. Multiple or vanished displays must never execute a command on a different
   target; repeated/expired messages must not repeat actions (controls Task 3).
4. Actual fullscreen may differ from requested state; timeout/rejection and
   local Escape must produce truthful feedback (controls Task 4).
5. Interrupted connections, page unmount, and React StrictMode must recover or
   release resources without duplicate polls or message listeners (all tasks,
   integrated browser verification in Task 5).

## File ownership and order

Paths in task plans are relative to `frontend/mission-planner` unless explicitly
rooted at the repository. Existing hook call sites retain their defaults except
Overview's explicit live option. New code follows current file/test patterns.

1. [Saved-state refresh tasks 1–2](2026-10-04-overview-window-sync-refresh.md):
   query observers/services, local-save race protection, and refresh browser
   regressions. This produces a useful independently testable synchronization
   fix.
2. [Display control tasks 3–4](2026-10-04-overview-window-sync-controls.md):
   message/session modules, two React hooks, fullscreen helper, Configuration
   card, and Overview integration. This consumes existing recenter behavior.
3. [Integrated acceptance task 5](2026-10-04-overview-window-sync-acceptance.md):
   real-request production browser journey, regression gates, and documentation.

Commit each task's working deliverable. Do not claim issue readiness until Task
5's evidence and independent review are complete. An unverified lane remains
pending rather than being inferred from fixtures or unrelated acceptance tools.

## Worktree and baseline

Use `/tmp/starlink-257`, branch `feat/257-overview-window-sync`. It already
includes PR 258's merge `c8a69d25ba1e58140424d87c644d8aacb62c9d54`. The
unchanged frontend passed 82 unit files / 619 tests and the production build;
see the
[investigation](../../reports/2026-10-04-overview-window-sync-investigation.md).

- [x] Before implementation, refresh `origin/dev` and reconcile any new changes.
      Preserve original checkout and all other worktrees.
- [x] Run `npm ci` in this worktree's frontend using the tracked lockfile.
      Record Node/npm versions; do not change dependency versions for this
      issue.
- [x] Run `./tools/verify frontend` here and record the baseline. If it differs
      from the recorded frontend tree, explain failures before product changes.

## Self-review and handoff

Coverage: the spec's saved-state and recovery requirements map to tasks 1–2;
presence, targeting, deadlines, and fullscreen map to tasks 3–4; real saves,
activation/switching/deactivation, continuity, and operator guidance map to
task 5. Each task declares its interfaces and executable verification commands.

One platform limitation is explicit in controls Task 4: an expired command is
never newly issued, but timing out cannot abort a native fullscreen request the
browser already accepted. Late replies cannot claim success; actual target
fullscreen events remain authoritative. Review this distinction with the plan.

The user approved this plan and selected one new session per task. Follow the
[session handoff protocol](2026-10-04-overview-window-sync-handoff.md) and the
[tracked progress record](2026-10-04-overview-window-sync-progress.md). Sessions
1–4 stop after their assigned task and prepare the next message. Session 5
completes acceptance preparation and hands off to fresh independent review. An
integration session resolves findings, creates/completes the PR, verifies the
final candidate, and merges into `dev` under the user's existing authorization.
