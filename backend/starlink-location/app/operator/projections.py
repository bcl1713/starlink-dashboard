"""Capture one Operator snapshot, then derive deterministic operational files."""

import hashlib
import json
from types import MappingProxyType

from .issue_activity import derive_issue_updates
from .models import SavedRecord
from .projection_models import (
    ActivityItem,
    Association,
    AssociationChange,
    FieldChange,
    ProjectionBundle,
    ProjectionManifest,
    RevisionIdentity,
)
from .queries import decode_document
from .references import MissionReferences
from .store import OperatorStore


def _rows(connection, sql, parameters, budget=None):
    result = connection.execute(sql, parameters)
    columns = [column[0] for column in result.description]
    rows = []
    for row in result:
        if budget is not None:
            # Include per-row overhead so tiny records cannot bypass the bound.
            budget[0] -= 256 + sum(
                (
                    len(value.encode("utf-8"))
                    if isinstance(value, str)
                    else len(value) if isinstance(value, bytes) else 16
                )
                for value in row
            )
            if budget[0] < 0:
                raise RuntimeError("Operator archive input size limit exceeded")
        rows.append(row)
    return columns, rows


def _canonical(value):
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _association(document):
    return Association(
        **{name: document[name] for name in ("mission_id", "leg_id", "scope")},
        **{
            name: document["payload"].get(name)
            for name in ("previous_leg_id", "next_leg_id")
        },
    )


def _fields(document):
    if document is None:
        return {}
    fields = {
        name: document[name]
        for name in (
            "record_type",
            "mission_id",
            "leg_id",
            "scope",
            "deleted",
        )
    }
    for group in ("time", "payload"):
        fields.update(
            {
                f"{group}.{name}": value
                for name, value in document[group].items()
                if name not in ("schema_version", "title", "note")
            }
        )
    return fields


def _activity(document, previous, store_id):
    before, after = _fields(previous), _fields(document)
    changes = {
        name: FieldChange(before=before.get(name), after=after.get(name))
        for name in sorted(before.keys() | after.keys())
        if previous is None or before.get(name) != after.get(name)
    }
    text_changes = [
        f"payload.{name}"
        for name in ("note", "title")
        if previous is None
        or previous["payload"].get(name) != document["payload"].get(name)
    ]
    fields = {
        name: document[name]
        for name in (
            "record_id",
            "record_type",
            "version",
            "previous_version",
            "command_id",
            "journal_seq",
            "operation",
            "reason",
            "reason_origin",
            "author",
            "provenance",
            "recorded_at",
            "time",
        )
    }
    return ActivityItem(
        **fields,
        identity=RevisionIdentity(
            store_id=store_id,
            record_id=document["record_id"],
            version=document["version"],
        ),
        retrospective=document["provenance"]["mutation_origin"] == "retrospective",
        title=document["payload"]["title"],
        association=AssociationChange(
            before=_association(previous) if previous else None,
            after=_association(document),
        ),
        changes=changes,
        text_changes=text_changes,
        description=f"{document['operation']}: "
        + (
            ", ".join(sorted(changes.keys() | set(text_changes)))
            or "No content fields changed"
        ),
    )


def capture_projection(
    store: OperatorStore,
    *,
    mission_id: str,
    include_audit: bool = False,
    include_events: bool = False,
    max_input_bytes: int | None = None,
) -> ProjectionBundle:
    """Pin H and copy rows in one read; release SQLite before diffs/serialization.

    Planning association resolution happens afterwards and is explicitly unpinned.
    It neither asserts cross-store atomicity nor suppresses retained Operator IDs.
    Capture times name retained revision time, never a new serialization clock.
    """
    budget = [max_input_bytes] if max_input_bytes is not None else None
    with store.connect() as connection:
        high_water = connection.execute(
            "SELECT coalesce(max(journal_seq), 0) AS high_water FROM revisions"
        ).fetchone()[0]
        identity = store.health()
        last = connection.execute(
            "SELECT recorded_at FROM revisions WHERE journal_seq=?", (high_water,)
        ).fetchone()
        current_columns, current_rows = _rows(
            connection,
            """
            WITH chosen AS (
                SELECT record_id, max(journal_seq) AS seq FROM revisions
                WHERE journal_seq<=? GROUP BY record_id
            ) SELECT v.* FROM revisions v JOIN chosen c ON v.journal_seq=c.seq
            WHERE v.mission_id=? AND v.deleted=0 ORDER BY v.record_id
        """,
            (high_water, mission_id),
            budget,
        )
        history_columns, history_rows = _rows(
            connection,
            """
            SELECT * FROM revisions WHERE journal_seq<=? AND record_id IN (
                SELECT record_id FROM revisions WHERE journal_seq<=? AND mission_id=?
            ) ORDER BY journal_seq
        """,
            (high_water, high_water, mission_id),
            budget,
        )

        event_data = None
        if include_events:
            # All event tables share this same SQLite read transaction and H.
            event_data = {
                "schema_version": 1,
                "capture_policy": "persisted_only; no_model_recalculation",
            }
            for label, table in (
                ("occurrences", "event_occurrences"),
                ("heads", "event_heads"),
                ("transitions", "event_transitions"),
                ("acknowledgments", "event_acknowledgments"),
                ("tiers", "event_tiers"),
            ):
                columns, rows = _rows(
                    connection,
                    f"SELECT * FROM {table} WHERE occurrence_id IN (SELECT occurrence_id FROM event_occurrences WHERE mission_id=?) ORDER BY occurrence_id, rowid",
                    (mission_id,),
                    budget,
                )
                event_data[label] = [dict(zip(columns, row)) for row in rows]
            for occurrence in event_data["occurrences"]:
                occurrence["event"] = json.loads(occurrence.pop("event_json"))

    current = [decode_document(row, current_columns) for row in current_rows]
    activity, audit, previous_by_id = [], [], {}
    documents = [decode_document(row, history_columns) for row in history_rows]
    updates = derive_issue_updates(
        [
            SavedRecord.model_validate(doc)
            for doc in documents
            if doc["record_type"] == "issue"
        ],
        store_id=str(identity.store_id),
    )
    for document in documents:
        previous = previous_by_id.get(document["record_id"])
        if document["mission_id"] == mission_id or (
            previous and previous["mission_id"] == mission_id
        ):
            item = _activity(document, previous, identity.store_id)
            metadata = updates.get(document["journal_seq"])
            item.issue_update = metadata
            activity.append(
                item.model_dump(
                    mode="json", exclude={"issue_update"} if metadata is None else set()
                )
            )
            if include_audit:
                audit.append(document)
        previous_by_id[document["record_id"]] = document

    files = {
        "operations/current.json": _canonical(current),
        "operations/activity.jsonl": b"".join(_canonical(item) for item in activity),
    }
    labels = {
        "operations/current.json": "current_state",
        "operations/activity.jsonl": "activity",
    }
    if include_audit:
        files["operations/audit.jsonl"] = b"".join(_canonical(item) for item in audit)
        labels["operations/audit.jsonl"] = "full_historical_audit"
    if event_data is not None:
        files["operations/events.json"] = _canonical(event_data)
        labels["operations/events.json"] = "persisted_event_history"
    checksums = {path: hashlib.sha256(body).hexdigest() for path, body in files.items()}
    references = MissionReferences()
    unresolved = []
    for document in current:
        association = references.resolve(SavedRecord.model_validate(document))
        if association["status"] != "resolved":
            unresolved.append({"record_id": document["record_id"], **association})
    manifest = ProjectionManifest(
        store_id=identity.store_id,
        api_epoch=identity.api_epoch,
        mission_id=mission_id,
        source_mode=identity.source_mode,
        simulation_run_id=identity.simulation_run_id,
        replay_run_id=identity.replay_run_id,
        mission_journal=identity.mission_journal,
        high_water=high_water,
        audit_included=include_audit,
        projections=labels,
        checksums=checksums,
        component_capture_times={
            "operator": last[0] if last else None,
            "planning": None,
        },
        source_capture_revisions={"operator": high_water, "planning": None},
        unresolved_associations=unresolved,
    )
    return ProjectionBundle(
        high_water=high_water,
        manifest=manifest,
        files=MappingProxyType(files),
        checksums=MappingProxyType(checksums),
        store_id=identity.store_id,
        api_epoch=identity.api_epoch,
        source_mode=identity.source_mode,
        simulation_run_id=identity.simulation_run_id,
    )
