# Operator records and durable journal — issue #362

Status: design approved for implementation planning; no product implementation
authorized. The review clarifications on automatic audit reasons and default
activity exports are included.

Parent: [#361](https://github.com/bcl1713/starlink-dashboard/issues/361). First
slice: [#362](https://github.com/bcl1713/starlink-dashboard/issues/362).
Baseline inspected: `origin/dev` at `a39b750d` (2026-10-17), including #348 and
issue #349. The detailed design is approved; the implementation plan requires
separate review and execution-method selection.

## Purpose and scope

Give a single communications mission manager, or a counterpart using another
browser, ordinary editable operational records backed by immutable history.
Preflight, between-leg, and postflight work are first-class. Operator owns
reported operational decisions; it does not control aircraft, verify actual
routing, or convert modeled transport availability into measured availability.

This specification covers schema, mutation/read contracts, persistence,
integration seams, and the aircraft-free test harness for #362. Calls,
conferences, participation, issues, and transport decisions remain separate
record types. Their complete workflows belong to later child issues. #362
supplies the common persistence service and a small feature-gated journal
editor/history view for browser acceptance. It does not implement the complete
Operator shell, reminders, call protection, or final package assembly.

Keep Overview passive and readable at a distance. Preserve Missions planning,
Configuration, existing preflight packages, and telemetry archives. Saving an
estimate never requires acknowledging uncertainty, predicted outages, or backup
gaps. Validate inputs and reference integrity separately from confidence.

## Decisions and alternatives

Use one local SQLite database containing current records, immutable full-state
revisions, transaction receipts, and explicit record relationships. A domain
service performs small synchronous transactions. Reads use ordinary
current-state queries. No event bus, aggregate framework, reducer registry,
replay-dependent startup, broker, new authentication service, or mandatory
background process.

A file-per-event journal would require custom atomicity and indexing. Sharing
the flight detector's ledger would entangle unrelated lifecycle and migration
rules. The chosen store reuses transactional patterns while remaining
independent. Typed domain payloads are versioned Pydantic contracts, not
arbitrary executable events. Adding call or issue behavior requires explicit
service code and tests.

## Logical records and history

`record_id` is a stable backend-generated UUID. `version` starts at 1 and
increments by exactly one on every accepted mutation. Operational lists contain
one current active record per logical ID. A correction replaces its projected
content, type, times, and association; it never creates a second operational
row. The history endpoint exposes all versions, original values, correction
reasons, authors, and tombstones in append order. Tombstones retain the last
content. Restore appends another active version after validating current
dependencies.

A call record represents the call; changing it appends that call's history. It
does not also create an unrelated editable "call updated" record. History rows
are the automatic audit events. Manual journal entries are a separate
`journal_entry` record type. Later activity feeds may show a saved action once
using its revision identity, but must label that as activity rather than a
second call. Completing a call never implicitly closes a conference.

## Review documents

These documents together define the proposed #362 design:

1. [Schema, timestamps, and associations](2026-10-17-operator-journal-schema.md):
   relational shape, logical records, provenance, and corrected associations.
2. [API and atomic transactions](2026-10-17-operator-journal-api.md): versioned
   requests, idempotency, conflicts, pagination, and commit boundaries.
3. [Recovery, migration, and validation](2026-10-17-operator-journal-recovery-validation.md):
   WAL, backups, retention, rollback, and simulation/browser acceptance.

## Integration boundaries verified against dev

| Existing component                                                              | Proposed Operator boundary                                                                                                    |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `app/mission/storage.py`, `repository_gate.py`                                  | Reuse mission/leg IDs, `load_mission_v2`, global then sorted mission locks; never duplicate mission CRUD                      |
| `app/mission/pop_status.py` (`PopStatusService.snapshot`)                       | Consume captured status with injected position/clock; no new discovery lookup from Operator reads                             |
| `app/mission/pop_forecast.py` (`forecast_for_mission`, `forecast_for_live`)     | Use existing route/config-aligned forecast entry points; no second predictor                                                  |
| `app/services/pop/models.py` (`PopForecast`, `PopTransition`, `PopObservation`) | Carry forecast revision, catalog fingerprint, crossing ID, UTC window and explicit observed/unknown state                     |
| `app/services/flight_events/live_adapter.py` (`FlightEventRuntime`)             | Read public runtime status/events; retain detector ownership of actual flight boundaries                                      |
| `app/services/flight_events/store.py` (`FlightEventStore`)                      | Read immutable source event ID/revision when needed; do not add Operator tables here or advance its outbox                    |
| `app/services/telemetry_archive/store.py`, `coordinator.py`                     | Consume capture IDs/revisions and availability; retain archive ownership of capture windows, sealing, gaps, and recovery      |
| `app/services/telemetry_archive/preparation.py` (`TelemetryPreparationService`) | Reuse existing asynchronous preparation/status/cancel/download lifecycle, pinning captures rather than recollecting telemetry |
| `app/services/telemetry_archive/package.py` (`build_telemetry_package`)         | Preserve manifest, checksums, source-mode checks and observed telemetry CSVs                                                  |
| `app/mission/package/preparation_routes.py`, `snapshot_export.py`               | Extend the established artifact preparation contract in #370; preserve current planning/telemetry behavior                    |

PoP advisories remain modeled. Unknown location/handover is not an outage;
Starshield is available unless disabled or deliberately marked down. Preserve
the existing full-window planning outage rule only when Starshield is the sole
usable transport; usable Ka or coordinated concurrency-only X protects the plan.
Do not persist each forecast refresh as an Operator action. Upcoming views read
existing predictions. An operator decision referencing a forecast saves its
source identity and the minimal advisory snapshot necessary to explain the
decision, excluding IP/raw telemetry. Unknown producer generation time remains
null; Operator cannot derive it from an ETA or manufacture historical knowledge.

Flight phase/leg changes update context through the existing runtime. They do
not reassign Operator records, close conferences, create manual events, or
trigger capture boundaries. Source flight events may be read alongside Operator
activity using namespaced IDs without importing every detector revision. If a
later child persists a source-derived Operator annotation, its adapter uses a
deterministic key derived from producer, source ID/revision and action; retries
append once. Source revisions remain in their originating store. Integration
failures are explicitly unknown/unavailable; no synthetic outage or success is
inserted.

### Export contract and consistent snapshots

Issue #362 provides a pure snapshot projection function used by tests; #370
wires it into the existing production preparation lifecycle. Do not introduce
another standalone export route/worker now. Current production accepts artifact
kinds `planning` and `telemetry`; adding an operations/combined artifact
requires an explicit compatible extension, not pretending it already exists.

The normal mission operations export must include both `operations/current.json`
(one latest active record per logical ID) and `operations/activity.jsonl`
(chronological operational changes). Current state alone is insufficient for
human/LLM after-action review. Optional CSV may mirror these separately labeled
projections. Only the full `operations/audit.jsonl`, containing original
full-state revisions, is separately requested. This is a required #362
projection contract and #370 production-integration handoff, not an optional
enhancement deferred for later design. Existing planning-only and telemetry-only
artifact contracts remain unchanged until that integration.

Derive activity deterministically from committed revisions at H; no extra event
store or write path. Emit one activity item per accepted record revision, keyed
by `(store_id, record_id, version)` with `command_id` and `journal_seq`.
Multiple items for one call describe changes to that call, not additional call
records. Each item carries schema version, record ID/type, version/predecessor,
operation, reason/origin, author, provenance/source mode, immutable
`recorded_at`, separate reported `occurred_at`/`ended_at` with precision,
planned times, and an explicit retrospective flag. Sort by acceptance sequence
(normally recording chronology), never backdate knowledge by sorting only on
actual occurrence. Include source observation/prediction times without inventing
missing values.

Include structured changed fields with before/after values for operational type,
status, schedule, actual interval/precision, mission/leg/scope, and typed
relationships. Creates supply initial values. Schedule shifts/cancellations,
issue opening/resolution/reopening, timing corrections, removal and restoration
remain reconstructable without full audit. A cancellation is a domain status
change; removal is a tombstone activity. Free-text edits identify changed fields
and that revision's title but need not copy every prior note into the timeline;
exact prior free-text bodies require audit. Display generated change
descriptions as such, not as operator-authored explanations.

For a late-entered 1430–1442Z call recorded at 1600Z, activity says when it was
reported and when it reportedly happened. A later 1545→1535 end-time correction
has a new item containing both values; current state has one corrected call.
Remove/restore items preserve their chronology even when the call is absent from
current state. Soft removal is not historical erasure.

A manifest names schema version, store ID, epoch, mission ID, source mode/run
ID, Operator high-water sequence, component capture times, source capture
revisions, checksums, mandatory activity inclusion, optional audit inclusion,
and unresolved associations. Include mission-only and between-leg records at the
mission root, not under an arbitrary leg. CSV uses existing formula-escaping
conventions. Label current state, activity, and full audit as distinct
projections.

Pin H and capture required Operator rows in one read transaction; select the
latest version per ID at H before filtering mission/deletion. Activity includes
revisions associated with the mission when accepted, plus a move-out item when
the predecessor belonged to it; the target mission receives the same move-in
identity. A move item carries before/after association. Do not include later
unrelated changes in the old mission. Audit includes that mission's historical
revision membership and move-out boundary. All projections use the same H;
removed records remain absent from current but their activities remain present.
Frozen projection bytes and fingerprints are persisted with the preparation job
before acknowledgment in #370; restart uses that snapshot, not a newly queried
live store. Pin the existing #349 capture revisions through its preparation
boundary. Independently record each component's capture point: there is no
universal atomic instant across independent stores. Hold the repository gate
only while pinning mission identity/configuration, then release before expensive
export work. Never hold the Operator write lock while calling archive services.
A partial/unavailable telemetry component retains its existing explicit labeling
and must not block exporting the Operator journal.

Simulation artifacts are conspicuously simulation-only and use separate stores.
The existing telemetry builder rejects non-live captures: preserve that guard.
Offline tests may use wholly synthetic samples labeled live in a disposable
operational-format test store to test that builder; evidence must still label
the fixture/test provenance as synthetic. A demo simulation package must not be
relabeled live to pass the guard. No change to import compatibility or claim of
operational re-import is included in #362; inspect/validate the JSON projection
for this slice, with import policy addressed explicitly by #370.

## Delivery and review boundary

This is an architectural design for #362, not a commitment to implement all nine
epic children in one branch. After design approval, write an implementation plan
with ordered schema/service/API, fixture, editor, integration, failure, and
production acceptance tasks. The plan must preserve the transaction invariants
and schema/API examples above; any discovered incompatibility returns for design
review before product changes. Record later child schema additions as forward
migrations rather than inventing a generic event platform in this foundation.
