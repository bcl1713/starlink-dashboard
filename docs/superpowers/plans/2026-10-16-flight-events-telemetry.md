# Flight Events and Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Detect departure and arrival ground phases and preserve the passenger-service telemetry window as durable, downloadable mission records.

**Architecture:** A persistent event ledger separates planned-leg identity from observed flight segments. A conservative movement detector feeds additive status fields; a durable capture service records pre-departure history and subsequent observations independently of temporary download preparation.

**Tech Stack:** Existing Python/FastAPI/Pydantic backend, Prometheus, backend-owned persistent storage, React/TypeScript frontend, pytest and Vitest. SQLite is proposed for transactional event/job metadata; immutable CSV chunks and manifests reside on a persistent local volume.

**Spec:** [Flight events and telemetry design](../specs/2026-10-16-flight-events-telemetry-design.md).

## Global Constraints

- Capture begins 30 minutes before actual off-blocks and ends 30 minutes after first confirmed destination parking.
- First confirmed destination parking includes a DV offload stop. Later repositioning does not reopen arrival or extend the recording tail.
- Movement before parking confirmation resets the candidate. A confirmed park is not revoked automatically by later movement.
- Operational fuel stops away from the destination remain within the same planned leg; time on the ground alone never splits a leg.
- Missing observations are not zero. GPS-derived events are inferences, not wheel-contact measurements.
- Operational routing, bandwidth control, and PoP prediction remain outside scope.
- Simulation data cannot enter live archives. Existing planning exports and legacy phase values remain compatible.

## Review Focus

- A DV offload stop followed by repositioning must retain its original park and capture end: Task 2.
- Startup without 30 minutes of available history must report a leading gap: Task 4.
- An intermediate fuel stop can exceed the ordinary parking dwell without completing the destination leg: Task 2.
- Public-IP label changes and multiple series must survive archival without being merged into invented transitions: Task 4.
- A correction after ZIP preparation must create a new revision while the original download remains stable: Task 5.

## Grounding and execution boundary

Planning inspected the repository's dev tree, workspace instructions, telemetry model, ETA service, Overview arrival projection/panel, Prometheus history reader, export-preparation documentation, and quality-gate guide. Earlier inspection covered the default-branch flight-state manager and status models. Reconcile those files against the execution checkout before editing.

This workspace contains planning artifacts, not a repository checkout. At execution, follow repository AGENTS.md: isolate a feature worktree based on origin/dev, preserve the primary checkout, and keep changes on a feature branch. Read managed-runtime and worktree skills before starting runtime resources. No code, tests, deployment, or PR is claimed complete by this plan.

Deliver three reviewable increments: events and arrival display (Tasks 1–3), durable capture (Task 4), and download integration (Tasks 5–6). This preserves working behavior at each increment without delaying the existing arrival bug behind archive packaging.

## File responsibilities

Backend paths below are relative to backend/starlink-location; frontend paths are relative to frontend/mission-planner.

Existing backend: app/services/flight_state/manager.py and checkpoint.py integrate detailed state without overloading the manager; app/models/flight_status.py and app/api/flight_status.py expose additive fields; app/services/overview_upcoming_pois.py and app/models/overview_upcoming_pois.py carry the state used by Overview; app/mission/package/preparation_routes.py and preparation_worker.py integrate the distinct telemetry export mode. Existing app/services/overview_history_prometheus.py is a reference for client configuration, not an archive reader to reuse unmodified: its projection discards ambiguous series and query-range evaluation times are not source observation times.

New backend modules: app/services/flight_events/models.py (typed contracts), detector.py (pure state transitions), store.py (transactional ledger), live_adapter.py (accepted live observation integration); app/services/telemetry_archive/reader.py (bounded raw source queries), store.py (durable chunks), coordinator.py (capture jobs), package.py (immutable CSV/ZIP assembly). Keep these small and cohesive.

Existing frontend: src/services/overview-upcoming-pois.ts and src/pages/overview-arrival.ts carry and project new state; src/pages/OverviewArrivalPanel.tsx renders it. Add src/services/telemetry-archives.ts for the telemetry preparation client. Place archive controls in the existing mission detail flow after auditing its export component.

## Task 1: Establish the live evidence contract and reproduce arrival failure

**Files:** Create tests/integration/test_live_flight_events.py and app/services/flight_events/models.py; inspect the flight manager, telemetry model, live collection entry point, Overview service, and deployment storage settings. Record findings in docs/reports/2026-10-16-flight-events-live-contract.md in the repository.

**Interfaces:** Define FlightObservation(observed_at, position_observed_at, speed_observed_at, altitude_observed_at, altitude_validity_source, latitude, longitude, speed_knots, altitude_feet, altitude_usable, source_mode, mission_id, leg_id, route_id), FlightEvent(kind, occurred_at, detected_at, source, confidence, evidence, revision), and DetectionPolicy. Nullable values remain nullable. Source mode is live or simulation. altitude_usable is true only when its own source validity and observation freshness pass; fresh position does not make altitude fresh. Event kinds are off_blocks, takeoff, landed, on_blocks, correction, and stop_classified.

- [ ] Trace real accepted telemetry into departure/arrival checks, through status and upcoming-POI snapshots into Overview. Identify exact ingestion call sites and mission binding ownership in the report before editing them.
- [ ] Add a failing integration case named test_live_arrival_away_from_endpoint: a previously airborne aircraft lands, taxis and stops more than 100 metres from the final waypoint; assert the detailed state eventually becomes parked and a positive landing countdown is absent.
- [ ] From backend context, run the focused integration test under a 10-minute timeout; record the actual failure before changing behavior.
- [ ] Define the typed contracts and synthetic observation fixtures. Preserve collection-time provenance: no field claims to represent receiver fix time unless the source supplies it.
- [ ] Document altitude validity, speed freshness, airport context availability, and active-leg ownership. Synthetic traces prove implementation behavior, not field accuracy. If usable altitude or airport context is unavailable, specify an uncertain/manual-confirmation path rather than claim automatic touchdown accuracy.
- [ ] Run model/fixture tests and commit the evidence contract separately.

## Task 2: Persistent event ledger and conservative movement detection

**Files:** Create app/services/flight_events/detector.py, store.py, live_adapter.py and tests/unit/test_flight_events.py; modify app/services/flight_state/manager.py and checkpoint.py; modify the accepted live ingestion call sites identified in Task 1.

**Interfaces:** advance_detection(state: DetectionState, observation: FlightObservation, policy: DetectionPolicy) -> DetectionResult; FlightEventStore.apply_observation(observation: FlightObservation) -> DetectionResult; FlightEventStore.correct_event(event_id: str, occurred_at: datetime, reason: str) -> FlightEvent. DetectionResult contains detailed_state, uncertainty, emitted_events, candidate_changes, and leg_completion. candidate_changes contains candidate identity, lifecycle action (created/reset/confirmed), evidence start and required history start. Persist candidate state and durable pin references atomically in the event store; capture buffer garbage collection respects these references even before confirmed-event delivery. DetectionState persists event candidates and their observation-time continuity. Stores transact on one observation identity at a time. Persist every event and an outbox entry in the same SQLite transaction. The capture consumer acknowledges an event only after idempotently persisting its work, keyed by event identity and revision; replay unacknowledged entries after restart.

- [ ] Add failing parametrized traces for parked→taxi_out→airborne→landed/rollout→taxi_in→parked, with event occurrence time distinct from confirmation time. Assert confirmed events retain the beginning of their qualifying evidence interval.
- [ ] Add test cases for go-around, airport overflight, slow airborne motion, GPS loss, stale speed, duplicate/out-of-order samples, airport-coordinate offset, and absent usable altitude. Assert no invented landing or parking.
- [ ] Add test_dv_offload_then_reposition: after a qualifying destination stop and subsequent 45-minute pause, later movement leaves the first on_blocks event unchanged. Assert the capture end remains on_blocks + 1800 seconds. Add a brief taxi-hold case that resets before confirmation.
- [ ] Add test_fuel_stop_keeps_leg_open and test_route_change_preserves_ownership. Away-from-destination parking cannot complete the leg; explicit diversion completion can. Restart restores confirmed state and resets any candidate whose continuity cannot be established.
- [ ] Run tests and record expected failures. Implement the pure detector, transactional SQLite ledger, deduplication, and live adapter. Preserve existing public phase values; add detailed states separately. No detector writes operational routing controls.
- [ ] Set initial policy values only after Task 1 evidence review. Proposed engineering defaults for test evaluation: movement above 3 knots for 15 seconds, airborne above 80 knots for 20 seconds with supporting altitude evidence, parking below 1 knot with positions within 50 metres for 300 seconds. These are configurable, unvalidated defaults, not universal aircraft rules. Landing evidence requires prior airborne state, coherent descent/leveling, and ground-speed behavior; speed alone is insufficient. Missing evidence produces uncertainty. Record the exact selected values and rationale in the live-contract report before implementation review.
- [ ] Add manual event correction and stop classification using persisted evidence and immutable revision records. Define FlightEventStore.record_manual_event(mission_id: str, leg_id: str, kind: EventKind, occurred_at: datetime, reason: str, actor: str) -> FlightEvent and classify_stop(stop_id: str, classification: StopClassification, reason: str, actor: str) -> FlightEvent. Supported stop classifications are intermediate and destination_complete. Validate authenticated operator identity, mission/leg ownership, timestamp ordering and allowed event transitions; reject conflicts explicitly. Manual creation must work when no inferred event exists. Feed manual events through the same durable outbox. Reconcile existing departure/arrival meanings with all consumers; retain their existing meanings and add explicit event timestamps rather than silently repurpose fields.
- [ ] Add startup-during-taxi and startup-airborne cases: restore persisted events when present; otherwise expose unknown departure/off-blocks and request manual historical events. Never derive an actual off-blocks time from process startup or route activation; unknown boundaries mean incomplete capture. Test fresh position and speed with stale altitude, asserting altitude cannot confirm airborne or landed.
- [ ] Run focused state, checkpoint, and flight-status regression tests; commit the event subsystem.

## Task 3: Additive API and departure/arrival presentation

**Files:** Modify backend app/models/flight_status.py, app/api/flight_status.py, app/models/overview_upcoming_pois.py, app/services/overview_upcoming_pois.py and corresponding existing tests. Modify frontend src/services/overview-upcoming-pois.ts, src/pages/overview-arrival.ts, OverviewArrivalPanel.tsx and their existing tests.

**Interfaces:** Add movement_state, movement_uncertain, movement_observed_at, off_blocks_at, takeoff_at, landed_at, on_blocks_at, and capture_state as optional response fields. Existing clients continue using unchanged flight_phase values. All fields in one Overview response refer to the same mission/leg snapshot.

- [ ] Add failing backend contract tests for the new fields, absent-field compatibility, and consistent mission binding.
- [ ] Add failing frontend cases: taxi out displays taxi status separately from scheduled takeoff; supported landing replaces the positive landing countdown; taxi in and parked have distinct labels; uncertainty/freshness suppress unsupported current-state certainty. Legacy responses retain current fallback behavior.
- [ ] Run focused tests to verify failures, then implement additive serialization and projection. Reuse the existing observation-age checks; do not treat an API refresh timestamp as proof of source freshness.
- [ ] Add authenticated POST /api/v2/missions/{mission_id}/legs/{leg_id}/flight-events accepting kind, occurred_at and reason, and POST /api/v2/missions/{mission_id}/legs/{leg_id}/stops/{stop_id}/classification accepting classification and reason. Resolve actor from the existing authenticated request context rather than user-supplied text; if this deployment has no authentication, use the existing authorized operator boundary and document that limit without claiming authenticated identity. Add operator controls for off-blocks, takeoff, landed, parked, event-time correction, intermediate stop and diversion completion. In this increment, show uncertainty and the target event revision; archive impact previews are introduced only after the capture service exists in Task 4. Add PATCH /api/v2/missions/{mission_id}/legs/{leg_id}/flight-events/{event_id} accepting expected_revision, occurred_at and reason. Resolve actor at the operator boundary. Validate event ownership and ordering across the leg, reject stale expected_revision with a conflict, preserve the original event identity and append an immutable correction revision through the outbox. Never select a correction target by event kind alone. Add a multi-segment leg test that corrects the second landing without modifying the first, plus stale-revision and cross-leg rejection tests.
- [ ] Test a wholly manual event sequence with unusable altitude/context, including creation of previously absent events, ownership rejection, ordering validation and durable outbox persistence. History recovery and missing-data assertions belong to Task 4, where the capture service is introduced.
- [ ] Run focused backend and frontend tests, then the applicable canonical verification tiers. Commit events/display as the first shippable increment.

## Task 4: Durable rolling buffer and resumable capture

**Files:** Create app/services/telemetry_archive/reader.py, store.py, coordinator.py, tests/unit/test_telemetry_archive.py and tests/integration/test_telemetry_archive_recovery.py. Modify backend lifecycle/ingestion owners identified in Task 1, app/core/config.py, docker-compose.yml and docs/setup/configuration/storage-configuration.md.

**Interfaces:** ArchiveReader.read(start: datetime, end: datetime, mode: str) -> ArchiveBatch; ArchiveStore.append(batch: ArchiveBatch) -> Checkpoint; CaptureCoordinator.apply_event(event: FlightEvent) -> CaptureState; CaptureCoordinator.recover(now: datetime) -> list[CaptureState]. ArchiveBatch preserves source metric name, allowlisted labels, scrape time, available source observation time, value and availability. CaptureState includes leg identity, bounds, revision, gaps, watermark and pending work.

- [ ] Add failing tests asserting start = off_blocks_at − 1800 seconds and end = first destination on_blocks_at + 1800 seconds. A later ground move does not change either bound. Overlapping planned-leg buffers preserve both windows with explicit shared coverage metadata.
- [ ] Add tests for short startup history, missing/stale/zero distinctions, public-IP changes, multiple label series, and simulation segregation. Assert secrets and non-allowlisted labels never reach files.
- [ ] Add restart/outage/failure-injection cases: crash after chunk publication but before watermark commit, unavailable Prometheus, disk full, retention expiry, corrected boundaries, and two competing workers. Assert idempotent samples, visible gaps, recoverable pending jobs, and exactly one published revision.
- [ ] Run failing tests. Implement a durable rolling pre-event buffer with at least 35 minutes retention and incremental extraction with bounded chunks, source sample identity and overlapping retry windows. Use raw range-vector samples where required to avoid fabricating scrape timestamps through query_range lookback. Record scrape time separately from application observation time.
- [ ] Use SQLite transactions for work ownership and watermarks, atomic chunk publication, and explicit recovery of orphaned writes. Pin chunks when an off-blocks candidate begins, including its preceding 30 minutes; keep them pinned until candidate rejection or capture ownership is durable. The extra five minutes is a recovery margin, not a replacement for pinning. Retain prebuffer chunks referenced by active captures or undelivered outbox events. On startup, recover candidate pins and consume pending events before buffer garbage collection. If downtime exceeds available history, report the exact gap. Delete only unreferenced expired buffer chunks; never auto-delete sealed mission archives under the buffer retention policy.
- [ ] Add tests with delayed off-blocks confirmation while Prometheus history is unavailable, asserting the complete 30-minute pre-event interval remains pinned. Inject crashes after event commit before delivery, after capture work commit before acknowledgement, and during correction delivery; assert replay creates exactly one capture revision and preserves its history.
- [ ] Complete the manual-only capture acceptance deferred from Task 3: create absent historical events, recover available history, and assert explicit gaps and correct capture revisions. Integrate archive impact previews into the manual correction UI now that capture state exists; display the affected revision and unrecoverable history without pretending absent source data can be recovered.
- [ ] Persist on a backend-owned mounted volume. Keep archive data independent of the existing 30-minute download-job expiration. Collection failure exposes archive health without changing operational controls. Retry recoverable failures with capped backoff and retain unresolved gaps rather than silently mark complete.
- [ ] Run focused recovery tests and backend tier; document volume ownership, backup and archive growth. Commit the independently testable capture service.

## Task 5: Versioned CSVs and mission telemetry packages

**Files:** Create app/services/telemetry_archive/package.py and tests/unit/test_telemetry_package.py; modify app/mission/package/preparation_routes.py, preparation_worker.py and their tests. Create frontend src/services/telemetry-archives.ts; modify the existing mission detail export UI after identifying its owning component.

**Interfaces:** prepare_telemetry_package(mission_id: str, revisions: tuple[str, ...], allow_partial: bool) -> PreparedTelemetryPackage. Extend preparation with artifact_kind='telemetry' while preserving the current planning default. Package inputs are pinned to sealed capture revisions. PreparedTelemetryPackage includes completeness, ordered leg manifests and immutable package location.

- [ ] Add failing tests for ordered two-leg ZIP content, schema version, UTC event boundaries, missing-data intervals, source mode, checksums, stable ZIP metadata and deterministic bytes for identical revisions.
- [ ] Add test_correction_does_not_mutate_prepared_download: correction produces a new capture revision and package; the prior ready download retains original bytes until its ordinary expiration. Expiration may remove the temporary ZIP but must preserve source archives.
- [ ] Add partial/incomplete mission, pending extraction, simulated capture and cancellation tests. Default completed export rejects silently incomplete content; explicit partial export labels it in status and manifest.
- [ ] Run failing tests; implement schema version 1 with observations.csv, events.csv and manifest.json per leg. Preserve ordered segments and stops, metric/label identity, null values, available provenance, and correction history. Protect CSV text cells against spreadsheet formula execution without changing numeric values.
- [ ] Integrate with existing preparation polling/cancellation and download behavior. Add a distinct telemetry action and display pending/partial/ready state. Reuse preparation machinery without coupling source archive lifetime to job cleanup.
- [ ] Run package, existing export-preparation and frontend mission detail regression tests. Commit the third functional increment.

## Task 6: End-to-end acceptance and execution handoff

**Files:** Create backend tests/integration/test_mission_telemetry_archive.py and frontend tests/e2e/overview-flight-events.spec.ts; update docs/development/mission-export-preparation.md and the flight-events report.

**Interfaces:** The public contracts from Tasks 1–5; no new runtime interface.

- [ ] Add a failing full-flow fixture for two legs including taxi out, flight, landing offset from the terminal coordinate, a DV offload park, later repositioning and a subsequent leg. Include an intermediate fuel stop within one leg. Assert first-park semantics, both buffers, mission ownership, UI state and ordered package contents.
- [ ] Execute the fixture through live-mode adapters with controlled synthetic source observations. Separately test simulation exclusion. Include backend restart and a bounded Prometheus outage near arrival.
- [ ] Verify archived CSVs after removing the test source's retained time range. Run focused suites, then repository canonical static, backend and frontend tiers with wall-clock limits and the required reviewed base revision.
- [ ] For UI changes, perform repository-required exact-revision browser acceptance at 1920×1080. Record evidence showing taxi out, landed/taxi in, parked, uncertain state and telemetry preparation. Do not present synthetic acceptance as real-flight calibration.
- [ ] Record actual results, unresolved field-calibration limits and storage configuration. Self-review spec coverage, signatures and archive ownership. Perform the selected execution method's independent code review before proposing integration.
- [ ] Stop and verify all task-owned runtime resources. Preserve review evidence and the open feature worktree. Submit changes against dev under repository workflow; merging or deploying is a separate action governed by user authorization.

## Plan self-review

All spec areas map to tasks: evidence and inference (1–2), compatibility and ETA (3), buffers/durability/gaps (4), schema/export/revisions (5), acceptance and rollout evidence (6). The DV-stop clarification overrides any earlier suggestion to wait for the final storage stand or revoke a confirmed park on movement. Threshold values remain explicitly unvalidated pending Task 1 evidence; inability to validate yields an uncertain/manual path, not fabricated confidence.

No runtime resources were started during planning. No production code or tests were changed. Execution must first reconcile these planning artifacts with the isolated repository checkout.

## Independent review resolution

Addressed all five independent-review findings in the plan: candidate-time history pinning with extra retention; transactional event outbox and idempotent delivery; manual creation/correction/classification endpoints and operator controls; altitude-specific freshness/provenance; and startup taxi/airborne behavior with explicit unknown bounds. Each has an acceptance test assigned above. These are planning revisions, not implemented or verified product behavior. Execution method selected by the user: native implementation, followed by independent branch review.

## Second independent review resolution

Second review found no architectural blocker. Clarified event-ID-addressed correction with optimistic revision validation and multi-segment tests; moved archive-dependent manual acceptance and impact UI from Task 3 to Task 4; made candidate lifecycle signals and atomic persistent pin ownership explicit. Review concluded another design review round is unnecessary for these narrow amendments. Native execution remains selected; implementation has not started.
