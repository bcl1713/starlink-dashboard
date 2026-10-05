# Mission-leg Simulation Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking. Execution method awaits the user's choice.

**Goal:** Replay a complete mission leg at a selected multiplier or target
runtime, with coherent events/timing and network telemetry cards hidden during
the run.

**Architecture:** Prepare one effective route and canonical event schedule, then
advance one transactional replay runtime from monotonic elapsed time. Real
observation timestamps remain separate from simulated mission time. The existing
background loop publishes replay frames; clients read confirmed snapshots.

**Tech Stack:** Python 3.11 locally, FastAPI/Pydantic 2, pytest,
React/TypeScript, React Query, Vitest, Playwright Chromium, production
Docker/Nginx/Prometheus.

**Spec:** Read the approved
[design](../specs/2026-10-05-mission-leg-simulation-speed-design.md) and
[acceptance contract](../specs/2026-10-05-mission-leg-simulation-speed-acceptance.md).

**Status:** Plan awaits user review and execution choice. No product code
exists. Continue in `.worktrees/262-simulation-speed` on
`feat/262-simulation-speed`; draft PR
[270](https://github.com/bcl1713/starlink-dashboard/pull/270) targets `dev`.

## Global constraints

- Multiplier: 0.1× through 1000×, inclusive; target runtime: at least one
  second.
- Explicit pacing starts immediately at adjusted planned departure; explicit 1×
  uses this behavior too. Bodyless activation preserves existing behavior.
- Process every canonical event once in order; finish at the final coordinate,
  100% progress, POST_ARRIVAL, without looping or reversing.
- Real UTC observation time governs freshness, telemetry/history, and ADS-B.
  Simulated mission time governs flight elapsed time, ETAs, and running clocks.
- Hide all five metric cards and network header only during confirmed `running`;
  restore on terminal/idle state; retain a compact terminal result.
- One-second visible run polling; three-second two-window acceptance ceiling.
  Stop extrapolating after ten real seconds or a failed refresh.
- One traversal; ephemeral pacing; no speed changes or pause/resume; no resumed
  run after service restart; retain at most one run per runtime owner.
- Controlled 120-second completion must be published within one second of its
  deadline; record lateness honestly and demonstrate supported rates.
- Keep production Dockerfiles, Nginx, daemon/context, shared configuration, and
  credentials. Use task-owned acceptance resources and exact candidate SHAs.
- New files stay focused and within applicable line limits; no unrelated splits,
  dependencies, warning suppression, production rollout, or automatic merge.

## Review focus

1. Previewing or failing a start must not modify POIs or destroy the prior run
   (Tasks 1 and 3: spy on writes and compare lifecycle snapshots).
2. Sparse anchors, antimeridian crossings, or inconsistent timing must never
   produce a different route/clock from the event plan (Tasks 1 and 2).
3. Fast replay and simultaneous events must preserve all transitions even when
   browser frames omit intermediate states (Task 2: canonical cursor
   assertions).
4. Restart and delayed responses must not resurrect hidden panels or stale runs
   (Tasks 3 and 5: incarnation/revision/request-generation tests).
5. Historical planned dates and terminal results must not invalidate real-time
   freshness or accidentally age the simulation clock (Tasks 4 and 5).

## Task order and file ownership

Tasks are sequential: 1 → 2 → 3 → 4 → 5 → 6. Complete each task's red/green
cycle and commit before review and the next task. Each linked task defines exact
files, interfaces, tests, and commands. Fixtures belong to the task needing
them.

| Task | Deliverable                                          | Instructions                                                                                         |
| ---- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 1    | Strict pacing and side-effect-free effective plan    | [Core tasks](2026-10-05-mission-leg-simulation-speed-core.md#task-1-pacing-and-effective-plan)       |
| 2    | Transactional clock, events, movement, final state   | [Core tasks](2026-10-05-mission-leg-simulation-speed-core.md#task-2-replay-runtime)                  |
| 3    | Preview/start/status APIs and lifecycle              | [Integration tasks](2026-10-05-mission-leg-simulation-speed-integration.md#task-3-api-and-lifecycle) |
| 4    | Flight, ETA, handoff, and real freshness integration | [Integration tasks](2026-10-05-mission-leg-simulation-speed-timing.md#task-4-two-time-domains)       |
| 5    | Controls, shared state, clocks, panel visibility     | [Frontend task](2026-10-05-mission-leg-simulation-speed-frontend.md)                                 |
| 6    | Production acceptance, docs, final review            | [Acceptance task](2026-10-05-mission-leg-simulation-speed-acceptance.md)                             |

## Public wire contract

Define closed Pydantic models in
`backend/starlink-location/app/models/simulation_run.py` and validated matching
TypeScript models in `frontend/mission-planner/src/services/simulation-run.ts`.
Numbers are strict finite JSON numbers, never coerced strings/booleans. Dates
are UTC ISO 8601. Reject unknown fields and discriminator variants.

```typescript
type PacingInput =
  | { mode: "multiplier"; multiplier: number }
  | { mode: "target_runtime"; runtime_seconds: number };
type RunState = "idle" | "running" | "completed" | "cancelled" | "failed";
type NormalizedPacing = {
  pacing: PacingInput;
  effective_multiplier: number;
  flight_duration_seconds: number;
  expected_runtime_seconds: number;
};
type SimulationPreview = NormalizedPacing & {
  plan_token: string;
  planned_departure: string;
  planned_arrival: string;
  limits: { min_multiplier: 0.1; max_multiplier: 1000; min_runtime_seconds: 1 };
};
type SimulationStart = { pacing: PacingInput; plan_token: string };
type ActivationRequest = { simulation?: SimulationStart };
type RunSnapshot = NormalizedPacing & {
  run_id: string;
  mission_id: string;
  leg_id: string;
  route_id: string;
  plan_token: string;
  planned_departure: string;
  planned_arrival: string;
  simulation_time: string;
  started_at: string;
  observed_at: string;
  finished_at: string | null;
  elapsed_real_seconds: number;
  completion_lateness_seconds: number | null;
  progress_percent: number;
  phase: "in_flight" | "post_arrival";
  processed_event_count: number;
  transport_states: { X: string; Ka: string; Ku: string };
  error: { code: string; message: string } | null;
};
type SimulationRunStatus = {
  runtime_id: string;
  revision: number;
  service_mode: "simulation" | "live";
  state: RunState;
  served_at: string;
  run: RunSnapshot | null;
};
```

Transport values are `available`, `degraded`, or `offline`. Idle has
`run: null`; other states have a run. Revision increases on accepted
frames/lifecycle changes, never on GET. `observed_at` is the last published real
observation; `served_at` cannot renew freshness. Startup generates a new opaque
`runtime_id` UUID. Cancelled/failed before arrival retain `in_flight` and last
confirmed context.

| Operation                                                             | Request                               | Success                                                                                  |
| --------------------------------------------------------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------- |
| `POST /api/v2/missions/{mission_id}/legs/{leg_id}/simulation/preview` | `PacingInput`                         | `SimulationPreview`                                                                      |
| Existing `POST .../activate`                                          | No body, `{}`, or `ActivationRequest` | Existing status/active-leg ID; add `simulation_run: SimulationRunStatus` for paced start |
| `GET /api/simulation/run`                                             | None                                  | `SimulationRunStatus`                                                                    |
| `GET /api/simulation/run/{run_id}/route`                              | None                                  | `{ runtime_id, run_id, route: RouteDetail }` for the selected effective route            |

Use 422 with field/message details for bad inputs or unusable timing; 409 for
live mode, preview mismatch, or incompatible running-plan edits; 503 before
readiness; preserve 404 for missing mission/leg. Include current runtime status
in conflicts when initialized so the UI can refresh safely.

Preview tokens are SHA-256 over stable canonical serialization of mission/leg
identity, effective route/timing, pacing, and event schedule. Exclude generated
POI UUIDs, observation/creation times, and collection metrics. Tokens are
content identities, not authorization. Revalidate before activation side
effects.

Fetch effective geometry once per runtime/run identity, separately from status
polling. This reuses the existing `RouteDetail` shape; normal route-detail APIs
still return stored plans. An unavailable/superseded run geometry returns 404.

## Preparation and review handoff

Before product work, inspect current `origin/dev` and reconcile upstream changes
in this isolated branch without discarding open-PR work. Record the base. Use
tracked Python 3.11 locally, frontend Node 22.22.2, and locked npm installation
with `--legacy-peer-deps`. CI sets up Python 3.13; record the interpreter
actually selected by each gate. Establish the existing backend/frontend baseline
before product edits; report failures with their scope.

Use `superpowers:executing-plans` if Native is selected, or
`superpowers:subagent-driven-development` if the user selects subagents. Review
this plan and select the method before product dependencies or code are changed.
The same draft PR can carry implementation after these gates; update its title,
description, review status, and exact-head evidence to match the finished
change.
