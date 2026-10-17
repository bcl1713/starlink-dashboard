# Operator journal — API and atomic transactions

Part of the [proposed #362 design](2026-10-17-operator-journal-design.md).
Status: for review; no product implementation authorized.

## Versioned HTTP API

Base: `/api/v2/operator`; body/response `schema_version: 1`. The URL's v2
follows the existing backend API namespace; payload version is independently
explicit. The service remains gated off by default (`OPERATOR_ENABLED=false`).
Reads and writes use the existing restricted-access boundary. No PWA, external
auth, push, HTTPS provisioning, or new infrastructure.

| Method and path              | Contract                                                                |
| ---------------------------- | ----------------------------------------------------------------------- |
| `POST /records`              | Create a typed record; returns 201 and saved version 1                  |
| `GET /records/{id}`          | Current saved record, including tombstone if removed                    |
| `PUT /records/{id}`          | Full editable-state replacement with expected version; returns 200      |
| `POST /records/{id}/remove`  | Expected version and optional audit note; appends tombstone             |
| `POST /records/{id}/restore` | Expected version and optional audit note; restores last content         |
| `GET /records?mission_id=…`  | Current active projection, optional scope/leg/type filters              |
| `GET /records/{id}/history`  | Explicitly labeled immutable audit versions                             |
| `GET /journal?mission_id=…`  | Mission audit stream in acceptance sequence                             |
| `GET /health`                | Store readiness, mode, schema version, clock/storage errors; no content |

Mutations require `Idempotency-Key` (client-generated UUID) and edits require
`expected_version` in the body. Mutation response includes `command_id`, saved
record/version, sequence, `recorded_at`, and schema version. Full replacement is
deliberate: omitted fields cannot silently retain old hidden values. Read ETags
may represent `record_id:version`, but body version is the single mutation
precondition. No blind PUT/upsert. Removed-record edits require restore first.
`GET /health` also supplies store ID and API epoch. All writes require
`X-Operator-Store-Epoch`; validate it before receipt replay. A mismatch returns
409 `store_epoch_changed` and requires client state reconciliation. The header
is a restore/session guard, not an authentication credential. Missing epoch
is 422. Epoch rotation happens under the same exclusive maintenance boundary
used to restore the database and must finish durably before the store reopens.

Update/remove/restore bodies accept optional `audit_note` (at most 1000
characters). Omitted or blank notes never cause validation failure: the backend
sets the automatic reason and origin defined in the schema document. A supplied
nonblank note is labeled operator-authored. Responses/history expose `reason`
and `reason_origin`; clients cannot claim an automatic reason was user-written.
The mobile editor saves routine changes directly, with an optional note in the
existing editor and no additional reason prompt or required field. The reason
and its origin are part of the same revision transaction, not a later write.

Example create (synthetic data only):

```json
{
  "schema_version": 1,
  "record_type": "journal_entry",
  "mission_id": "demo-mission",
  "leg_id": null,
  "scope": "between_legs",
  "time": {
    "occurred_at": "2026-10-17T14:30:00Z",
    "ended_at": "2026-10-17T14:42:00Z",
    "precision": "exact",
    "end_state": "known",
    "planned_start_at": null,
    "planned_end_at": null
  },
  "payload": {
    "schema_version": 1,
    "entry_type": "call_observation",
    "title": "Demo unscheduled call",
    "note": "Entered after completion",
    "previous_leg_id": "demo-leg-a",
    "next_leg_id": "demo-leg-b"
  },
  "operator_label": "Demo operator"
}
```

`journal_entry` supports `note` and `call_observation` initially; the latter is
a retrospective observation, not the future scheduled-call domain object. #362
defines typed fixture payloads for calls/conferences/issues/participation/risk
and transport reports to exercise persistence and links through internal service
tests. Public CRUD for these types is enabled only with the respective child
workflow; requests cannot smuggle arbitrary payloads through the note endpoint.

Errors have
`{error: {code, message, fields?, current_version?, record_ids?, retryable}, request_id}`.
Never return internal paths, SQL, notes, or sensitive payloads in logs. Return
422 for genuine input errors, 404 for absent records, 409 `version_conflict`,
`idempotency_conflict`, `dependency_conflict`, or `invalid_transition`, and 503
for store busy/unavailable/full/read-only/corrupt or unsupported schema. Missing
expected version/key is 422. Busy is retryable with `Retry-After: 1`;
unavailable storage requires an explicit readiness recovery. Unknown commit
outcome returns 503 `commit_outcome_unknown` when a response is possible. Client
preserves its draft and key, labels status unconfirmed, and retries the exact
command. It never displays "saved" on send or HTTP timeout.

Successful receipts are retained for the store's lifetime. An exact retry
returns the original saved status/body even if a newer version now exists, with
`Idempotency-Replayed: true`. The client subsequently reads current state.
Reusing a key for different canonical method/path/body returns 409; the hash
includes expected version and all normalized semantic inputs, excluding
transient request IDs. Check successful receipt before version/association
checks. Failed validation/conflict commands do not consume the key. Never rebase
and resubmit a conflicting edit automatically; fetch the latest and ask the
operator to reconcile.

Lists default to 50, maximum 200. Use opaque versioned cursors, not OFFSET. For
stable paging, the first request captures committed maximum `journal_seq` H;
each page selects the latest revision per ID at or below H, then applies
mission/scope/type/deleted filters. Cursor includes store ID, H, filter hash,
and last record ID; order by record ID. Invalid cursor is 422. This is a
snapshot of current state at H, so moves/edits during paging cannot duplicate or
omit rows. History/journal pages similarly pin H and order by sequence.
`include_removed` is explicit; default false. Return H and `as_of`. Current
unpaged record reads return the latest committed value. No wall-clock ordering
assumption is required.

## Atomic command execution

One application service owns all Operator mutations, including later call/issue
updates. They must not write to separate files or stores and then "log"
afterward.

1. Validate and canonicalize the typed request and derive its request hash. Read
   an existing receipt first; an exact committed retry needs no planning access.
   A new command proceeds with the canonical repository gate
   `get_active_leg_lock()`, followed by affected mission locks in sorted ID
   order, then the Operator database transaction. Recheck the receipt inside it.
2. Use bounded lock waits (repository/mission up to 2 seconds; SQLite busy
   timeout 2 seconds). Under `BEGIN IMMEDIATE`, validate existing mission/leg
   identities, current record versions, mode, and all incoming/outgoing
   dependencies. Never take repository locks while holding a database write
   transaction.
3. Build the complete next revision, allocate sequence, and insert it. Advance
   the current pointer conditionally on the expected version, and replace the
   affected current link rows. A multi-record domain action, when introduced by
   a child issue, validates all versions and appends all affected revisions
   under the same command/transaction. No partial success response.
4. Insert the command receipt containing the exact success body, including all
   saved versions and timestamps. Its deferred FK permits insertion after the
   revision rows. COMMIT, release locks, then acknowledge success. Any failure
   before commit rolls back history, projection, links, and receipt together.
5. Client invalidation/cues happen after acknowledgment. Future durable reminder
   deliveries, if needed, must be rows in this same transaction; #362 adds no
   generic outbox. No external call runs inside this transaction.

Do not mutate an observed flight event using this command API. Existing flight
commands retain their own transaction/history. The guarantee here covers an
Operator-owned state change and its audit rows; it does not claim atomicity
across SQLite databases, mission JSON, export files, or external equipment.
