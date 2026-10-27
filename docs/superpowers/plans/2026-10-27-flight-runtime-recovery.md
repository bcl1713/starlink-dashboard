# Flight Runtime Recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this integrated
> fix.

**Goal:** Restore reliable live detector/archive lifecycle and observable
recovery.

**Architecture:** One lifecycle owner reconciles the existing runtime and tracks
stage health. Configuration switches actual sources; durable event persistence
remains authoritative for arrival and captures.

**Tech Stack:** Python 3.11, FastAPI, SQLite, React/TypeScript, pytest, Vitest.

**Spec:** docs/superpowers/specs/2026-10-27-flight-runtime-recovery-design.md

## Global Constraints

- Preserve operational data, archive boundaries, manual correction and
  provenance.
- Never record simulation as live or silently infer live arrival via 100 m
  dwell.
- Keep diagnostics in mission planning/settings; no Overview diagnostic panels.
- Retry initialization after 5 seconds with exponential backoff capped at 60
  seconds.
- Use isolated resources with wall-clock bounds, cleanup and exact-SHA evidence.
- Branch from origin/dev and open PR to dev; no production changes or merge.

## Review Focus

- Mode switches must replace the actual source, refresh all API owners and
  exclude simulation.
- Storage recovery must retain leg identity and avoid duplicate
  clients/workers/events.
- Failure of event persistence must never manufacture phase confirmation.
- Frozen evidence and sustained descent/climb must not be treated as landing
  stability.
- Healthy dashboard metrics must not conceal unavailable detection/capture.

### Task 1: Runtime lifecycle, storage and source integration

**Files:** app/services/flight_events/lifecycle.py (new), live_adapter.py,
app/api/config.py, app/api/health.py, main.py, entrypoint.sh; tests in
backend/starlink-location/tests/unit and tests/integration.

**Interfaces:** app.state.flight_event_lifecycle owns initialization and stage
health; app.state.flight_event_runtime remains the compatible durable runtime.
`reconcile(mode: str)` returns the ready runtime or None. `status()` returns
sanitized availability and recovery fields. Configuration callback on app.state
updates application source bindings under the existing active-leg lock.

- [ ] Write tests for simulation/live POST and PUT, bounded transient/persistent
      failure recovery, history preservation, sample/event failure isolation and
      no automatic live legacy fallback. Run them and observe expected failures.
- [ ] Implement owner with safe construction/close and stage health, integrate
      startup/config/tick/shutdown, source replacement, health/status API and
      mount setup.
- [ ] Run focused lifecycle/config/event/source-admission regressions and
      commit.

### Task 2: Landing evidence and complete-flight acceptance

**Files:** flight_events/models.py, detector.py, store.py if needed; existing
and new detector and live integration tests.

**Interfaces:** Existing DetectionPolicy, FlightObservation, DetectionState,
FlightEventRuntime; preserve event occurrence/detection times and capture
policy.

- [ ] Add failing behavioral tests for frozen altitude timestamps and sustained
      trends; retain noisy/sloping runway control, gap/go-around and full flight
      outside endpoint circle with phase/ETA/archive provenance assertions.
- [ ] Implement minimal evidence continuity/stability corrections; keep current
      configurable thresholds, uncertainty and manual reconciliation semantics.
- [ ] Run detector/archive/Overview arrival tests, self-review and commit.

### Task 3: Planner disclosure, guidance and delivery

**Files:** MissionFlightEvents.tsx, services/telemetry-archives.ts, planner
tests; docs/troubleshooting and operator guidance; change-scoped acceptance
evidence.

**Interfaces:** GET /api/flight-recording/status exposes lifecycle health
without requiring a mission leg. Planner displays sanitized stage
availability/retry messages; existing event and correction API remains
compatible.

- [ ] Write failing planner tests for unavailable/degraded/recovering detection
      and capture, retained history in simulation, estimated occurrence vs
      confirmation.
- [ ] Implement planner status and document mode/storage diagnostics, recovery,
      inference defaults/geography and missing history/manual reconciliation.
- [ ] Run canonical gates and isolated production/browser acceptance; preserve
      evidence and verify teardown. Request independent whole-branch review,
      address findings, then push feature branch and open PR against dev.
