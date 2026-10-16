# Flight Events and Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Detect departure and arrival ground phases and preserve the
passenger-service telemetry window as durable, downloadable mission records.

**Architecture:** A persistent event ledger separates planned-leg identity from
observed flight segments. A conservative movement detector feeds additive status
fields; a durable capture service records pre-departure history and subsequent
observations independently of temporary download preparation.

**Tech Stack:** Existing Python/FastAPI/Pydantic backend, Prometheus,
backend-owned persistent storage, React/TypeScript frontend, pytest and Vitest.
SQLite is proposed for transactional event/job metadata; immutable CSV chunks
and manifests reside on a persistent local volume.

**Spec:**
[Flight events and telemetry design](../specs/2026-10-16-flight-events-telemetry-design.md).

## Global Constraints

- Capture begins 30 minutes before actual off-blocks and ends 30 minutes after
  first confirmed destination parking.
- First confirmed destination parking includes a DV offload stop. Later
  repositioning does not reopen arrival or extend the recording tail.
- Movement before parking confirmation resets the candidate. A confirmed park is
  not revoked automatically by later movement.
- Operational fuel stops away from the destination remain within the same
  planned leg; time on the ground alone never splits a leg.
- Missing observations are not zero. GPS-derived events are inferences, not
  wheel-contact measurements.
- Operational routing, bandwidth control, and PoP prediction remain outside
  scope.
- Simulation data cannot enter live archives. Existing planning exports and
  legacy phase values remain compatible.

## Review Focus

- A DV offload stop followed by repositioning must retain its original park and
  capture end: Task 2.
- Startup without 30 minutes of available history must report a leading gap:
  Task 4.
- An intermediate fuel stop can exceed the ordinary parking dwell without
  completing the destination leg: Task 2.
- Public-IP label changes and multiple series must survive archival without
  being merged into invented transitions: Task 4.
- A correction after ZIP preparation must create a new revision while the
  original download remains stable: Task 5.

## Grounding and execution boundary

Planning inspected the repository's dev tree, workspace instructions, telemetry
model, ETA service, Overview arrival projection/panel, Prometheus history
reader, export-preparation documentation, and quality-gate guide. Earlier
inspection covered the default-branch flight-state manager and status models.
Reconcile those files against the execution checkout before editing.

This workspace contains planning artifacts, not a repository checkout. At
execution, follow repository AGENTS.md: isolate a feature worktree based on
origin/dev, preserve the primary checkout, and keep changes on a feature branch.
Read managed-runtime and worktree skills before starting runtime resources. No
code, tests, deployment, or PR is claimed complete by this plan.

Deliver three reviewable increments: events and arrival display (Tasks 1–3),
durable capture (Task 4), and download integration (Tasks 5–6). This preserves
working behavior at each increment without delaying the existing arrival bug
behind archive packaging.

## File responsibilities

Backend paths below are relative to backend/starlink-location; frontend paths
are relative to frontend/mission-planner.

Existing backend: app/services/flight_state/manager.py and checkpoint.py
integrate detailed state without overloading the manager;
app/models/flight_status.py and app/api/flight_status.py expose additive fields;
app/services/overview_upcoming_pois.py and app/models/overview_upcoming_pois.py
carry the state used by Overview; app/mission/package/preparation_routes.py and
preparation_worker.py integrate the distinct telemetry export mode. Existing
app/services/overview_history_prometheus.py is a reference for client
configuration, not an archive reader to reuse unmodified: its projection
discards ambiguous series and query-range evaluation times are not source
observation times.

New backend modules: app/services/flight_events/models.py (typed contracts),
detector.py (pure state transitions), store.py (transactional ledger),
live_adapter.py (accepted live observation integration);
app/services/telemetry_archive/reader.py (bounded raw source queries), store.py
(durable chunks), coordinator.py (capture jobs), package.py (immutable CSV/ZIP
assembly). Keep these small and cohesive.

Existing frontend: src/services/overview-upcoming-pois.ts and
src/pages/overview-arrival.ts carry and project new state;
src/pages/OverviewArrivalPanel.tsx renders it. Add
src/services/telemetry-archives.ts for the telemetry preparation client. Place
archive controls in the existing mission detail flow after auditing its export
component.

## Task 1: Establish the live evidence contract and reproduce arrival failure

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-1.md) and
      record verification.

## Task 2: Persistent event ledger and conservative movement detection

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-2.md) and
      record verification.

## Task 3: Additive API and departure/arrival presentation

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-3.md) and
      record verification.

## Task 4: Durable rolling buffer and resumable capture

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-4.md) and
      record verification.

## Task 5: Versioned CSVs and mission telemetry packages

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-5.md) and
      record verification.

## Task 6: End-to-end acceptance and execution handoff

- [x] Execute the
      [detailed task steps](2026-10-16-flight-events-telemetry-task-6.md) and
      record verification.

## Plan self-review

All spec areas map to tasks: evidence and inference (1–2), compatibility and ETA
(3), buffers/durability/gaps (4), schema/export/revisions (5), acceptance and
rollout evidence (6). The DV-stop clarification overrides any earlier suggestion
to wait for the final storage stand or revoke a confirmed park on movement.
Threshold values remain explicitly unvalidated pending Task 1 evidence;
inability to validate yields an uncertain/manual path, not fabricated
confidence.

No runtime resources were started during planning. No production code or tests
were changed. Execution must first reconcile these planning artifacts with the
isolated repository checkout.

## Independent review resolution

Addressed all five independent-review findings in the plan: candidate-time
history pinning with extra retention; transactional event outbox and idempotent
delivery; manual creation/correction/classification endpoints and operator
controls; altitude-specific freshness/provenance; and startup taxi/airborne
behavior with explicit unknown bounds. Each has an acceptance test assigned
above. These are planning revisions, not implemented or verified product
behavior. Execution method selected by the user: native implementation, followed
by independent branch review.

## Second independent review resolution

Second review found no architectural blocker. Clarified event-ID-addressed
correction with optimistic revision validation and multi-segment tests; moved
archive-dependent manual acceptance and impact UI from Task 3 to Task 4; made
candidate lifecycle signals and atomic persistent pin ownership explicit. Review
concluded another design review round is unnecessary for these narrow
amendments. Native execution remains selected; implementation has not started.
