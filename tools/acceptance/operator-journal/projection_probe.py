"""Inspect default artifacts and explicit audit separately using production code."""

import hashlib
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.operator.models import CreateRecord, RemoveRecord, UpdateRecord
from app.operator.projections import capture_projection
from store_probe import open_service


def send(service, command):
    return service.execute(
        command, key=str(uuid4()), epoch=str(service.store.health().api_epoch)
    ).saved_records[0]


def change(service, row, **values):
    body = {
        n: getattr(row, n)
        for n in ("record_type", "mission_id", "scope", "leg_id", "time", "payload")
    }
    return send(
        service,
        UpdateRecord(
            record_id=row.record_id, expected_version=row.version, **(body | values)
        ),
    )


def inspect(bundle):
    current = json.loads(bundle.files["operations/current.json"])
    activities = [
        json.loads(line)
        for line in bundle.files["operations/activity.jsonl"].splitlines()
    ]
    assert len(current) == len({row["record_id"] for row in current})
    assert all(not row["deleted"] for row in current)
    assert [row["journal_seq"] for row in activities] == sorted(
        row["journal_seq"] for row in activities
    )
    assert bundle.manifest.high_water == bundle.high_water
    assert bundle.manifest.source_capture_revisions["operator"] == bundle.high_water
    assert bundle.manifest.component_capture_times["planning"] is None
    for name, content in bundle.files.items():
        assert hashlib.sha256(content).hexdigest() == bundle.checksums[name]
    return {
        "manifest": bundle.manifest.model_dump(mode="json"),
        "files": {name: content.decode() for name, content in bundle.files.items()},
    }


def main():
    with tempfile.TemporaryDirectory(prefix="operator-projections-") as root:
        service = open_service(Path(root))
        try:
            call = send(
                service,
                CreateRecord(
                    record_type="call",
                    scope="mission",
                    mission_id="synthetic-mission-a",
                    time={"planned_start_at": "2026-10-17T14:00:00Z"},
                    payload={"entry_type": "call", "title": "Synthetic scheduled call"},
                ),
            )
            call = change(
                service, call, time={"planned_start_at": "2026-10-17T14:10:00Z"}
            )
            call = change(
                service,
                call,
                payload={
                    "entry_type": "call",
                    "title": "Synthetic scheduled call",
                    "status": "cancelled",
                },
            )
            removed = send(
                service,
                CreateRecord(
                    record_type="journal_entry",
                    scope="mission",
                    mission_id="synthetic-mission-a",
                    time={
                        "occurred_at": "2026-10-17T14:30:00Z",
                        "ended_at": "2026-10-17T14:42:00Z",
                        "precision": "exact",
                        "end_state": "known",
                    },
                    payload={
                        "entry_type": "note",
                        "title": "Synthetic removed late report",
                        "note": "Historical synthetic note",
                    },
                ),
            )
            send(service, RemoveRecord(record_id=removed.record_id, expected_version=1))
            moved = send(
                service,
                CreateRecord(
                    record_type="journal_entry",
                    scope="mission",
                    mission_id="synthetic-mission-a",
                    time={},
                    payload={"entry_type": "note", "title": "Synthetic move"},
                ),
            )
            moved = change(service, moved, mission_id="synthetic-mission-b")
            change(
                service,
                moved,
                payload={"entry_type": "note", "title": "Synthetic B only"},
            )
            a = capture_projection(service.store, mission_id="synthetic-mission-a")
            b = capture_projection(service.store, mission_id="synthetic-mission-b")
            assert a.high_water == b.high_water
            assert "operations/audit.jsonl" not in a.files
            rows = [
                json.loads(line)
                for line in a.files["operations/activity.jsonl"].splitlines()
            ]
            call_rows = [r for r in rows if r["record_id"] == str(call.record_id)]
            assert (
                call_rows[1]["changes"]["time.planned_start_at"]["after"]
                == "2026-10-17T14:10:00.000000Z"
            )
            assert call_rows[2]["changes"]["payload.status"] == {
                "before": "scheduled",
                "after": "cancelled",
            }
            late = [r for r in rows if r["record_id"] == str(removed.record_id)]
            assert [r["operation"] for r in late] == ["create", "remove"]
            assert late[0]["recorded_at"] == "2026-10-17T16:00:00.000000Z"
            assert late[0]["time"]["occurred_at"] == "2026-10-17T14:30:00.000000Z"
            assert (
                b"Historical synthetic note" not in a.files["operations/activity.jsonl"]
            )
            boundary_a = [r for r in rows if r["record_id"] == str(moved.record_id)]
            boundary_b = [
                json.loads(line)
                for line in b.files["operations/activity.jsonl"].splitlines()
                if json.loads(line)["record_id"] == str(moved.record_id)
            ]
            assert [r["version"] for r in boundary_a] == [1, 2]
            assert [r["version"] for r in boundary_b] == [2, 3]
            assert boundary_a[-1]["identity"] == boundary_b[0]["identity"]
            audit = capture_projection(
                service.store, mission_id="synthetic-mission-a", include_audit=True
            )
            assert audit.high_water == a.high_water
            assert b"Historical synthetic note" in audit.files["operations/audit.jsonl"]
            result = {
                "defaultA": inspect(a),
                "defaultB": inspect(b),
                "explicitAudit": inspect(audit),
            }
        finally:
            service.store.close()
    # Also inspect the actual rows created through Nginx/browser, without mutating them.
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore
    from scenario import RUN_ID, ScenarioClock

    storage.MISSIONS_DIR = Path("/app/data/missions")
    store = OperatorStore.open(
        OperatorSettings(
            enabled=True,
            root=Path("/app/data/operator"),
            source_mode="simulation",
            simulation_run_id=RUN_ID,
        ),
        initialize=False,
        clock=ScenarioClock(),
    )
    try:
        result["browserCurrentAndActivity"] = inspect(
            capture_projection(store, mission_id="synthetic-mission-a")
        )
    finally:
        store.close()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
