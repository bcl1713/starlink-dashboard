# Itinerary and X band planning implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Create missions from itineraries and per-leg KMLs, then review ARs and
X-band proposals under the user's Starshield preference.

**Architecture:** A typed planning manifest holds expected legs and drafts
without weakening executable-leg requirements. Pure extraction, matching,
evaluation, and optimization feed revision-checked persistence operations.
Shared policy intervals drive previews, reviewed timelines, and exports.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, existing pypdf, filelock,
React/TypeScript, TanStack Query, Vitest, and the repository acceptance tools.
No new PDF, solver, database, or queue dependency is required.

**Spec:**
[Approved design](../specs/2026-10-09-itinerary-xband-planning-design.md) and
[required contracts](../specs/2026-10-09-itinerary-xband-planning-contracts.md).
Read both before implementing any task. This plan awaits user review and an
execution-method choice; approval of the spec did not approve this plan.

## Global constraints

- Starshield is preferred whenever usable; X-band yields in conflict areas.
- PDF uploads: 10 MiB; parsing deadline: 10 seconds.
- Optimizer deadline: 30 seconds; no partial optimum on timeout.
- Normal conflict 135–225 degrees; AR exclusion 315–45 degrees.
- Minimum elevation 10 degrees; swap degradation 15 minutes on each side.
- Shared 60-second candidate cadence plus exact boundaries; half-open intervals.
- Safety advice alone adds no X outage seconds; retain physical capability.
- Preserve manual locks, exact unlocked swaps, evaluation context, and sources.
- No preview writes, fake route/satellite IDs, new activation gate, or terminal
  commands. Legacy callers retain compatible inputs and response fields.
- Use task worktrees based on origin/dev. PRs target dev; never merge to main.
- Tests need wall-clock limits, owned resources, signal cleanup, and verified
  teardown. Preserve the actor's Docker daemon/context and shared credentials.

## Review focus

- Two tabs editing one leg: stale apply/save returns 409 without overwriting
  either installed work or unrelated metadata. Pinned by Tasks 3 and 7.
- A reviewed leg reopened with missing/deleted satellite data: show Needs review
  and unavailable calculation rather than substituting X-1. Tasks 5 and 7.
- Retry after crash during reviewed publication: reconcile owned writes before
  serving readers, with no half-installed plan. Tasks 3 and 10.
- Existing filename-derived route shared with another mission: replacement,
  import, retirement, and deletion never remove that other binding. Task 9.
- PDF extraction recognizes leg text but cannot recognize its AR section: do not
  call it an AR-free leg. Tasks 2 and 4.

## Delivery sequence and verification commands

Execute these linked plans in order; task numbers continue across documents:

1. [Import and AR review](2026-10-09-itinerary-xband-import.md): Tasks 1–4.
   Delivers persistent itinerary creation, uploads, and AR correction. A manual
   X draft is usable; automatic proposals remain unavailable until Task 7.
2. [Evaluation and optimization](2026-10-09-itinerary-xband-evaluation.md):
   Tasks 5–7. Delivers policy scoring, proposals, locks, and reviewed save.
3. [Recovery and acceptance](2026-10-09-itinerary-xband-recovery.md): Tasks
   8–10. Delivers revision/replacement, complete packages, and production
   acceptance.

Backend commands below run from `backend/starlink-location/`:

```bash
timeout --kill-after=10s 10m uv run --python 3.11 --with-requirements requirements.txt pytest tests/planning -q
```

Frontend commands run from `frontend/mission-planner/`:

```bash
timeout --kill-after=10s 10m npm run test:unit -- src/components/planning src/services/planning.test.ts
```

Use each task's focused selection during red/green cycles. Expected red is a
missing behavior/assertion failure, not dependency or environment failure. After
green, commit the task with the specified message; do not install shared runtime
resources or run acceptance until the task requires them.

## Wire and persistence conventions

All new operations use prefix `/api/v2/missions/planning`. APIs return typed
Pydantic schemas mirrored in `frontend/.../src/types/planning.ts`. UTC
timestamps serialize as ISO-8601. Source hashes are SHA-256; revision is a
positive integer. IDs are generated opaque UUID strings; filenames never become
resource IDs.

| Operation            | Method and suffix                                                  | Request → response                                         |
| -------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------- |
| Extract itinerary    | POST `/itinerary-previews`                                         | PDF multipart → ItineraryPreview                           |
| Satellite options    | GET `/satellite-options`                                           | none → PlanningSatelliteOptions                            |
| Confirm/create       | POST `/missions`                                                   | ConfirmItinerary → PlanningView                            |
| Read/resume          | GET `/missions/{mission_id}`                                       | none → PlanningView                                        |
| Bind/stage KML       | POST `/missions/{mission_id}/legs/{leg_id}/route-previews`         | KML multipart plus expected_revision → RouteBindingPreview |
| Accept route binding | POST `/missions/{mission_id}/legs/{leg_id}/route`                  | AcceptRouteBinding → PlanningView                          |
| Save draft           | PUT `/missions/{mission_id}/legs/{leg_id}/draft`                   | SaveDraft → PlanningView                                   |
| Availability preview | POST `/missions/{mission_id}/legs/{leg_id}/preview`                | PreviewDraft → PlanningEvaluation                          |
| Compute proposal     | POST `/missions/{mission_id}/legs/{leg_id}/proposals`              | GenerateProposal → PlanningProposal                        |
| Read proposal        | GET `/missions/{mission_id}/legs/{leg_id}/proposals/{proposal_id}` | none → PlanningProposal                                    |
| Apply proposal       | POST `/missions/{mission_id}/legs/{leg_id}/apply`                  | ApplyProposal → PlanningView                               |
| Reviewed save        | POST `/missions/{mission_id}/legs/{leg_id}/reviewed`               | SaveReviewed → PlanningView                                |
| Revision preview     | POST `/missions/{mission_id}/itinerary-previews`                   | PDF multipart plus expected_revision → RevisionPreview     |
| Apply revision       | POST `/missions/{mission_id}/revision`                             | ApplyRevision → PlanningView                               |

Every mutating request carries `expected_revision`; apply/reviewed requests also
carry `input_identity`. Confirm/create carries `preview_id` and corrected
extracted data, permitted satellite IDs/access confirmation and operational
`starshield_enabled` (default true for creation). Confirm/create has no existing
mission revision to match. Route acceptance carries `preview_id` and explicit
discrepancy acknowledgments. Store previews under task/mission staging with a
24-hour expiry; preview GET/POST computation does not modify executable mission
state.

Malformed inputs return 422; missing objects 404; stale/active conflicts 409;
unavailable computation 503. Deadline errors include `code` and `retryable`.
Uploads reject oversize bytes before parsing. Expired previews return 409 with
an action to reupload; idempotency keys prevent duplicate accepted creations.

Planning data is typed on load and stored in
`mission.metadata.itinerary_planning`; preserve other metadata. PlanningView
contains the parent mission, manifest revision, expected leg cards, per-leg
review/computation status, errors, and links to installed executable legs. The
companion plans define domain types and module interfaces.

For planning-managed legs, existing leg PUT/DELETE require optional query
parameters `expected_revision` and `input_identity`; absent/stale values return
409 with a reload action. They use the planning commit gate and invalidate or
archive planning records as specified in Tasks 7–9. These parameters remain
optional for unmanaged legs, whose historical behavior/response is retained.
Parent metadata updates preserve server-owned planning data; callers cannot
replace the manifest through ordinary mission metadata writes.

Distinguish two identities: EvaluationContext.input_identity hashes immutable
route/height/AR/configuration/policy/locks and persisted seed C/B, excluding the
selected unlocked schedule. Each leg card's input_identity additionally hashes
its selected draft schedule and confirmations. Proposals reference the source
draft identity; reviewed records reference the installed schedule identity.
Apply changes the draft identity/revision but preserves evaluation context. This
distinction prevents stale manual work from being applied while keeping the
accepted grid stable. Unknown versions fail with explicit migration errors.

## Coverage and completion

Tasks 1–4 cover extraction, confirmation, matching, draft state, and resume.
Tasks 5–7 cover every policy/grid/optimizer/manual-edit requirement. Tasks 8–9
cover revision, route history, retirement, ownership, and packages. Task 10
verifies the rendered end-to-end workflow, legacy compatibility, runtime
shutdown, and exact-candidate production evidence.

Final review requires all linked-task checks and acceptance evidence from the
same clean candidate, then a PR against dev. Stop runtime resources immediately
after checks. Retain open-PR worktrees and source evidence. Merge only under the
repository's review/check rules; user design approval is not PR merge approval.
