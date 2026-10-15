# Issue 257 session-by-session handoff protocol

The user approved the design and implementation plan and explicitly selected one
new session per task, continuing until the feature's PR is reviewed and merged
into `dev`. This protocol records that choice and supersedes skill defaults that
run all tasks continuously or ask for an integration choice again.

## Shared context and authorization

Repository: `bcl1713/starlink-dashboard`; original checkout:
`/home/oracle-worker/Work/starlink-dashboard`. Implementation worktree:
`/tmp/starlink-257`; branch: `feat/257-overview-window-sync`.

PR 258 already merged; the branch includes its merge
`c8a69d25ba1e58140424d87c644d8aacb62c9d54`. Do not wait for PR 258 or redo its
work. The design and plan gates are complete. Do not restart brainstorming,
rewrite approved requirements, or ask for the execution-method choice again.

The user authorizes implementation, relevant tests, task commits, push to the
feature branch, PR creation/review fixes, and merge of the verified PR into
`dev`. Required checks and review remain gates. This does not authorize
deployment, promotion to `main`, overwriting shared branches, bypassing branch
protection, destructive cleanup, or unrelated issue work.

## Read at every session start

1. Applicable `AGENTS.md`, runtime instructions, and
   `docs/development/cloud-docker.md`.
2. [Approved design](../specs/2026-10-04-overview-window-sync-design.md).
3. [Main plan](2026-10-04-overview-window-sync.md), including Global Constraints
   and Review Focus.
4. [Tracked progress](2026-10-04-overview-window-sync-progress.md), including
   prior rulings, commits, and unresolved findings.
5. The assigned task's exact section in the linked task plan. Inspect adjacent
   interfaces as needed; do not repeat completed tasks.

Verify worktree/branch, HEAD, remote state, and status before edits. Continue
using the existing worktree; do not change the original checkout's branch or
create another nested worktree. If using a different machine/environment, fetch
the feature branch into an isolated worktree and verify the handoff's commits
are present. Missing commits/artifacts are a concrete handoff blocker, never a
reason to silently start the task from another branch.

## Execution in each implementation session

Use `superpowers:executing-plans`, adapted to the user's one-task-per-session
choice, together with TDD, systematic debugging when needed, and verification
before completion. Complete only the assigned task. Preserve shared progress and
evidence for the next session; do not follow generic instructions to run all
remaining tasks or delete the overall plan workspace at a task boundary.

Task headings live in the task-specific files rather than the main index. If
using task-brief/task-start helpers, give them the file containing the assigned
heading. Keep their per-file scratch ledgers supplemental to the single tracked
cross-session record.

Resolve routine implementation defects in the plan against the approved spec and
observed code. Record each necessary deviation and its rationale; do not weaken
acceptance or silently substitute fixtures for a real-backend lane. Stop for
genuinely missing input or unsatisfied required gates, describing the specific
blocker. Otherwise progress within the user's existing authorization.

Task 1 performs the main plan's initial setup and baseline once. Later sessions
reuse it and verify changes relevant to their task. Preserve Docker's configured
DOCKER_HOST/context and runtime proxy/CA trust. Use only task-isolated
acceptance projects, volumes, and loopback ports.

## Completion and handoff contract

Before advancing: required task tests ran and passed; expected failing tests
were observed before their fixes; material defects are resolved; changes are
committed; task status/commands/results/evidence/rulings are recorded. Do not
claim complete from an agent report, cached results, or an unverified diff.

Commit code, task checkbox updates, and the progress entry. Push the feature
branch when possible so subsequent environments can fetch it. If normal push is
rejected, inspect the remote and reconcile; do not force-push without explicit
authorization. If push or evidence transfer is blocked, state it in the next
message and provide the recoverable local commit/artifact paths.

At the end, print a ready-to-paste next-session message. It must include:

- Repository, worktree, branch, PR URL if one exists, and required current SHA.
- Approved plan/design and this protocol, with paths from repository root.
- Assigned next stage and exact task file/heading.
- What is complete, interface changes/rulings, and unresolved findings.
- Tests run with results and durable evidence locations; any runtime setup
  needed to rerun them. Identify environment-local artifacts honestly.
- The one-task scope and the same requirement to produce the next handoff.
- The inherited PR/merge authorization and required exact-head checks/review.

Preserve the worktree for successor sessions. If the task remains incomplete,
generate a continuation handoff for the same task and say why; do not label it
Task N+1. Never advance solely because a session is ending.

## Stage order

| Session     | Work                                     | Next handoff                                      |
| ----------- | ---------------------------------------- | ------------------------------------------------- |
| 1           | Refresh plan Task 1 and initial setup    | Task 2                                            |
| 2           | Refresh plan Task 2                      | Task 3                                            |
| 3           | Controls plan Task 3                     | Task 4                                            |
| 4           | Controls plan Task 4                     | Task 5                                            |
| 5           | Acceptance plan Task 5, steps 1–6        | Independent whole-branch review                   |
| Review      | Acceptance Task 5 step 7 review          | PR/merge integration                              |
| Integration | Review fixes, final checks, PR and merge | Completion, or precise blocked-stage continuation |

Implementation task sources:

- [Refresh tasks 1–2](2026-10-04-overview-window-sync-refresh.md).
- [Controls tasks 3–4](2026-10-04-overview-window-sync-controls.md).
- [Acceptance task 5](2026-10-04-overview-window-sync-acceptance.md).

The review session uses a fresh context to review the whole feature against the
approved spec/plan, current `dev` diff, Review Focus, tests/evidence, and
recorded rulings. Use the code-review skill; report severity, file/line, effect
on the operator, reproduction, and requested correction. Record findings in
tracked progress, then hand off to integration. Self-review by the task's author
is not a substitute for this stage. Material fixes affecting the reviewed
behavior require a fresh follow-up review handoff before merge.

The integration session resolves findings, verifies affected tests, and creates
or completes one feature PR against `dev`, referencing issue 257. Review/PR
operations may precede final acceptance to provide durable evidence locations.
Reconcile current `dev` without force-pushing; if rebasing a published branch
would require force, merge `origin/dev` into the feature branch instead.

Freeze the final candidate before final acceptance. Record final-run artifacts
outside the tracked tree or on the PR so saving evidence does not silently
change HEAD. Any subsequent commit requires fresh exact-head required checks and
the corresponding acceptance/review verification. Check branch protection,
required CI and mergeability on the actual PR head; never bypass them or
describe unrelated acceptance as this feature's evidence.

After every applicable required check, production/browser acceptance, and
independent review passes, merge the PR into `dev` using the normal repository
merge method, without another generic permission menu. The original user
explicitly selected this outcome. Verify GitHub reports merged, record PR URL,
head/merge SHA and remaining limitations, and report completion. If a required
check/review cannot pass, keep the PR open and provide a concrete integration
continuation instead of claiming success.

## Initial Task 1 message

Copy the following into a new session connected to the same repository:

```text
Begin implementation of GitHub issue #257 in bcl1713/starlink-dashboard.

Use the existing worktree /tmp/starlink-257 and branch
feat/257-overview-window-sync. The original checkout is
/home/oracle-worker/Work/starlink-dashboard. PR #258 has already merged into
dev and is included; do not wait for it. The branch contains investigation
commit b2792bc5, plan commit 4e09b8d8, and the later session-handoff commit.
Verify HEAD/status/history before editing and preserve other worktrees.

The design and implementation plan are approved. I explicitly choose one
new session per implementation task, then separate fresh review and PR/merge
sessions. Do not restart design approvals or execute the whole plan in this
session. My authorization covers implementation, feature-branch commits/push,
PR creation, review fixes, and merge into dev after required checks and
acceptance/review pass. Do not deploy or promote to main.

Read these repository-relative files:
- AGENTS.md and docs/development/cloud-docker.md
- docs/superpowers/specs/2026-10-04-overview-window-sync-design.md
- docs/superpowers/plans/2026-10-04-overview-window-sync.md
- docs/superpowers/plans/2026-10-04-overview-window-sync-handoff.md
- docs/superpowers/plans/2026-10-04-overview-window-sync-progress.md
- docs/superpowers/plans/2026-10-04-overview-window-sync-refresh.md

Implement only Task 1, "Deliver scoped background refresh", plus the main
plan's initial setup/baseline. Use executing-plans adapted to the one-task
session scope, TDD, systematic debugging when needed, and verification before
completion. No product implementation is complete yet. Previously, the
unchanged frontend passed 82 files/619 tests and a production build; establish
the baseline in this worktree before edits. The stale-clock reproduction used
controlled API fixtures and does not establish production acceptance.

Follow Task 1's exact interfaces and tests. Complete its background refresh
and two-page regressions, preserve Configuration drafts/camera/history state,
and retain one polling owner per query. Resolve routine plan defects against
the approved spec and code, recording rulings rather than silently weakening
requirements. Preserve the configured Docker endpoint/context and isolated
runtime resources.

When Task 1 verification passes, commit its code and checkbox/progress updates,
push the feature branch if available, and stop at that task boundary. Print
a ready-to-paste Task 2 handoff containing the current SHA, completed work,
interface changes/rulings, exact test results/evidence, unresolved issues,
worktree/branch, and the approved plan/protocol paths. Instruct Task 2 to do
the same for Task 3, continuing through Tasks 4 and 5, independent review,
and PR/merge integration. If Task 1 is blocked or incomplete, provide a
Task 1 continuation instead of advancing. Do not delete shared progress,
evidence, or the implementation worktree.
```
