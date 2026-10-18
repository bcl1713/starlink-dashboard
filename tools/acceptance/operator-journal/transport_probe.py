"""Inspect actual decision revisions and reuse crash barriers with multi-service writes."""

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4


def atomicity(root):
    import store_probe
    from app.operator.models import CreateRecord

    previous_root, previous_command = store_probe.ROOT, store_probe.command
    command = CreateRecord(
        record_type="transport_decision",
        mission_id="synthetic-mission-a",
        scope="mission",
        time={},
        payload={
            "entry_type": "transport_decision",
            "title": "Synthetic atomic transport move",
            "services": [
                {
                    "row_id": str(uuid4()),
                    "service": name,
                    "applied": {"transport": "Ka"},
                }
                for name in ("VTC", "IPTV")
            ],
        },
    )
    store_probe.ROOT, store_probe.command = Path(root), lambda: command
    try:
        results = {
            barrier: store_probe.crash(barrier)
            for barrier in ("before_commit", "after_commit")
        }
        for barrier in results:
            service = store_probe.open_service(Path(root) / barrier)
            try:
                with service.store.connect() as db:
                    rows = db.execute(
                        "SELECT payload_json FROM current_records WHERE record_type='transport_decision'"
                    ).fetchall()
                    assert (
                        len(rows) == 1 and len(json.loads(rows[0][0])["services"]) == 2
                    )
            finally:
                service.store.close()
        return results
    finally:
        store_probe.ROOT, store_probe.command = previous_root, previous_command


def main():
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store, verify_store
    from store_probe import open_service, CLOCK

    root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
    service = open_service(root)
    try:
        with service.store.connect() as db:
            records = db.execute(
                "SELECT record_id,version,payload_json FROM current_records WHERE record_type='transport_decision'"
            ).fetchall()
            assert len(records) >= 3
            rows = db.execute(
                "SELECT * FROM revisions WHERE record_type='transport_decision' ORDER BY journal_seq"
            ).fetchall()
            links = db.execute(
                "SELECT * FROM current_links ORDER BY from_id,relation,to_id"
            ).fetchall()
        from app.operator.projections import capture_projection

        projected = capture_projection(
            service.store, mission_id="synthetic-mission-b", include_audit=True
        )
        normal_example = next(
            item
            for item in json.loads(projected.files["operations/current.json"])
            if item["record_type"] == "transport_decision"
        )
        historical_example = next(
            r.model_dump(mode="json")
            for record_id, _version, _payload in records
            for r in service.history(record_id).items
            if r.payload.entry_type == "transport_decision"
            and any(row.checked for row in r.payload.services)
        )
        manifest = backup_store(
            service.store,
            directory=service.store.settings.database_path.parent / "transport-backups",
        )
        restored = restore_store(service.store.settings, manifest=manifest, clock=CLOCK)
        assert restored.ready
        service.store.close()
        service = open_service(root)
        assert verify_store(service.store).ready
        with service.store.connect() as db:
            assert (
                db.execute(
                    "SELECT * FROM revisions WHERE record_type='transport_decision' ORDER BY journal_seq"
                ).fetchall()
                == rows
            )
            assert (
                db.execute(
                    "SELECT * FROM current_links ORDER BY from_id,relation,to_id"
                ).fetchall()
                == links
            )
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        with tempfile.TemporaryDirectory(
            prefix="synthetic-transport-crash-"
        ) as scratch:
            crashes = atomicity(scratch)
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "decisions": len(records),
                    "immutableRevisions": len(rows),
                    "backupRestore": True,
                    "linksRecovered": True,
                    "normalOperationsExample": normal_example,
                    "operatorCheckedHistoryExample": historical_example,
                    "multiServiceCommitBarriers": crashes,
                }
            )
        )
    finally:
        service.store.close()


if __name__ == "__main__":
    main()
