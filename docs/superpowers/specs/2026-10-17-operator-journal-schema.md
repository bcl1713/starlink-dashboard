# Operator journal — Schema, timestamps, and associations

Part of the [proposed #362 design](2026-10-17-operator-journal-design.md).
Status: for review; no product implementation authorized.

## Database schema

Proposed path: `data/operator/operations.sqlite3` on the existing local writable
data volume, outside mission directories, flight ledgers, and archive databases.
Live and simulation use separate paths/volumes. No network filesystem support.
Directories are private to the service; database/backup files use mode `0600`
and the directory `0700`, subject to the existing deployment ownership model.

The following is the normative relational shape, not a ready-to-run migration.
All UUIDs and UTC strings are canonicalized by strict application validation;
all JSON is validated against its named versioned payload schema. Migration SQL
must additionally install the constraints and triggers described below.

```sql
CREATE TABLE store_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    store_id TEXT NOT NULL UNIQUE,
    source_mode TEXT NOT NULL CHECK (source_mode IN ('live', 'simulation')),
    simulation_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE commands (
    command_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    request_hash TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    response_status INTEGER NOT NULL,
    response_json TEXT NOT NULL CHECK (json_valid(response_json))
);

CREATE TABLE revisions (
    journal_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    previous_version INTEGER,
    command_id TEXT NOT NULL REFERENCES commands(command_id)
        DEFERRABLE INITIALLY DEFERRED,
    operation TEXT NOT NULL CHECK
        (operation IN ('create', 'update', 'remove', 'restore')),
    reason TEXT,
    schema_version INTEGER NOT NULL,
    record_type TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    leg_id TEXT,
    scope TEXT NOT NULL CHECK
        (scope IN ('mission', 'preflight', 'leg', 'between_legs', 'postflight')),
    deleted INTEGER NOT NULL CHECK (deleted IN (0, 1)),
    recorded_at TEXT NOT NULL,
    author_json TEXT NOT NULL CHECK (json_valid(author_json)),
    time_json TEXT NOT NULL CHECK (json_valid(time_json)),
    provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    UNIQUE (record_id, version),
    FOREIGN KEY (record_id, previous_version)
        REFERENCES revisions(record_id, version)
);

CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    current_version INTEGER NOT NULL,
    FOREIGN KEY (record_id, current_version)
        REFERENCES revisions(record_id, version)
);

CREATE VIEW current_records AS
SELECT v.* FROM records r JOIN revisions v
    ON v.record_id = r.record_id AND v.version = r.current_version;

CREATE TABLE current_links (
    from_id TEXT NOT NULL REFERENCES records(record_id),
    relation TEXT NOT NULL,
    to_id TEXT NOT NULL REFERENCES records(record_id),
    PRIMARY KEY (from_id, relation, to_id),
    CHECK (from_id <> to_id)
);

CREATE INDEX revisions_mission_seq ON revisions(mission_id, journal_seq);
CREATE INDEX revisions_command ON revisions(command_id);
CREATE INDEX links_target ON current_links(to_id);
```

The current-state projection is a pointer to a complete validated revision, not
a separately maintained copy of every payload. Thus a current call or issue
cannot exist without its exact audit row. No revision replay is needed to load
current state. `current_links` is a transactionally maintained index of the
typed relationships also captured in each revision payload. It is never an
independent source of meaning. Initial supported relations are
call-to-conference and participation-to-call/conference; later types add
explicit named relations. Historical links use the revision payload, not today's
link index.

Required constraints/triggers:

- Reject UPDATE and DELETE on `revisions` and `commands` in normal operation.
- A create has version 1 and null predecessor. Other revisions have predecessor
  `version - 1`, which must be the record's current version at insertion.
- A record pointer may only advance by one to the just-inserted revision; record
  deletion is forbidden. Insert pointers only at version 1. Transaction tests
  verify no orphan revisions or stale pointers after each service command.
- `scope = leg` requires `leg_id`; other scopes require null `leg_id`. Optional
  between-leg context uses `previous_leg_id` and `next_leg_id` in the typed
  payload, validated against the same mission. Scope is explicit, never inferred
  from whichever leg is active when the browser submits.
- Require nonempty reason for corrections, remove, restore, association changes,
  and type changes. Enforce bounded reasons (1–1000 characters), titles (1–200),
  notes (at most 8000), and entire request bodies (64 KiB). Reject unknown
  fields.
- Foreign-key enforcement is enabled on every connection. Cross-store mission
  references are validated under repository locks, not fabricated SQL FKs.

Audit immutability protects against application mistakes. It is not a
tamper-proof or authenticated ledger against an administrator with database file
access.

## Time, attribution, and provenance contracts

Every response includes the complete saved time and provenance objects:

| Field                                     | Meaning and ownership                                               |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `time.occurred_at`                        | Reported actual start/instant, nullable when unknown                |
| `time.ended_at`                           | Reported actual end, nullable for ongoing/unknown end               |
| `time.precision`                          | `exact`, `approximate`, or `unknown`; unknown has null actual times |
| `time.end_state`                          | `instant`, `ongoing`, `known`, or `unknown`                         |
| `time.planned_start_at`, `planned_end_at` | Scheduled/forecast interval, separate from actual times             |
| `provenance.observed_at`                  | Source observation time, nullable if unavailable                    |
| `provenance.predicted_at`                 | Time the source produced the forecast, nullable if unavailable      |
| `recorded_at`                             | Immutable backend acceptance time for this revision                 |
| `author`                                  | Backend attribution plus optional operator display label            |
| `provenance.kind`                         | `operator_reported`, `observed`, or `modeled`                       |
| `provenance.source_mode`                  | Backend-selected `live` or `simulation`                             |
| `provenance.source_ref`                   | Optional typed producer ID, source record/revision and fingerprint  |

For an operator entry, `recorded_at` is when the backend accepted the entry, not
when the operator began typing. No authoritative client entry timestamp is
needed. Operator-reported actual time remains explicitly reported, not verified.
Observed and forecast source times are carried unchanged by trusted adapters;
editing an observed assertion creates an operator-reported revision preserving
its source reference. A browser cannot claim to be a telemetry or model
producer. Author labels are self-reported: the application currently has no
built-in user authentication. Reuse its restricted LAN boundary and fixed
backend attribution; never treat a caller header or label as authenticated
identity.

Accept RFC 3339 aware datetimes with `Z` or explicit offset, normalize to UTC
with fixed microsecond precision and `Z`, and reject naive values. All displays
label UTC. Validate actual and planned ends against their respective starts. A
known end requires an actual start and end; ongoing requires a start and null
end; unknown end is allowed; instant has a start and no end. Unknown precision
requires unknown end state. Approximate times are estimates, not exact
measurements. Planned times can exist without actual times. Future plans use
planned fields; future actual times beyond a 60-second clock tolerance return a
field error. Unknown source timestamps remain null, never replaced by occurrence
time.

One injected `Clock` supplies acceptance/observation/simulation time; use a
monotonic source for wait deadlines. Persist store mode and simulation run ID;
refuse startup against a mismatched mode. Clock rollback does not reorder
history: `journal_seq` establishes acceptance order, and a clock-regression
health advisory exposes the condition without rewriting accepted timestamps.
Staleness is computed on read from source time and a producer-specific
threshold. Return `fresh`, `stale`, or `unknown` with the threshold and `as_of`;
no time means unknown. Acceptance time never proves source freshness.

At 1600Z, entering a call that happened 1430–1442Z creates one record with that
actual interval and a 1600Z acceptance time. History and exports state it was
entered later. Correcting an end from 1545Z to 1535Z creates version 2 with a
new acceptance time. The regular view shows 1535Z once; audit keeps 1545Z. An
"as known then" audit query uses the acceptance sequence, never actual time.
Later reminders must use current planned state and an explicit scheduling
action; backfill, correction, restore, and source-history import never emit
past-due alerts. #362 returns mutation origin (`interactive`, `retrospective`,
or `source_sync`) as backend-derived metadata in the revision provenance.

## Associations and dependency integrity

Reuse `Mission.id` and `MissionLeg.id` from `app/mission/models.py`, resolved by
`load_mission_v2`. No requirement for an active route, flight phase, or active
leg. Store mission ID on every revision. Historical IDs remain intelligible even
if planning data later disappears; reads label unresolved references and never
silently attach an entry to the new active leg.

An association correction is one normal versioned update. Validate the target
mission/leg under repository gates, preserve the old association in history, and
atomically update the current projection and links. Both old and new mission
views are invalidated. Ordinary reads/export membership follow the current
association. Audit membership includes revisions whose mission ID matched at
that time and explicitly labels subsequent movement; current content in another
mission is available through record history, not presented as a current entry.

An unlinked record may move missions. A linked record may move legs within its
mission if its typed constraints remain valid. Cross-mission moves or type
changes that would invalidate any incoming/outgoing relationship return
`409 dependency_conflict` with affected record IDs. The operator first edits or
removes relationships through normal audited updates; there is no cascade move,
cascade delete, or hidden batch rewriting. A removed referenced conference/call
is rejected until dependencies are explicitly detached or removed. Restore
revalidates targets and fails explicitly if they no longer exist or are removed.
Any active dependent cannot point to a removed record. Removed children do not
block parent removal, but retain their historical relationships.

Mission/leg removal from the planning store is not distributed-transactionally
coupled to this database. Preserve Operator records independently and flag
missing associations on reads. Reject new edits targeting absent associations;
allow reassociation to valid IDs or removal. Existing command retries remain
readable even if an association subsequently disappears. No implicit data purge
occurs on mission deletion. A future coordinated deletion workflow must preserve
this explicit retention boundary rather than deleting Operator files
incidentally.
