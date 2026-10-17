"""Inspect browser-created call corrections through production projections."""

import json
import os
from pathlib import Path

from app.mission import storage
from app.operator.projections import capture_projection
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import RUN_ID, ScenarioClock


def main():
    root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
    storage.MISSIONS_DIR = root / "missions"
    store = OperatorStore.open(
        OperatorSettings(
            enabled=True,
            root=root / "operator",
            source_mode="simulation",
            simulation_run_id=RUN_ID,
        ),
        initialize=False,
        clock=ScenarioClock(),
    )
    try:
        bundle = capture_projection(
            store, mission_id="synthetic-mission-a", include_audit=True
        )
        current = json.loads(bundle.files["operations/current.json"])
        history = [
            json.loads(line)
            for line in bundle.files["operations/audit.jsonl"].splitlines()
        ]
        retro = [
            row
            for row in current
            if row["record_type"] == "call"
            and row["time"]["occurred_at"] == "2026-10-17T14:30:00.000000Z"
        ]
        assert len(retro) == 3
        for row in retro:
            assert row["payload"]["prep_lead_minutes"] is None
            assert row["time"]["planned_start_at"] is None
            assert row["time"]["ended_at"] == "2026-10-17T14:45:00.000000Z"
            revisions = [
                revision
                for revision in history
                if revision["record_id"] == row["record_id"]
            ]
            assert revisions[0]["time"]["ended_at"] == "2026-10-17T14:42:00.000000Z"
            assert any(revision["operation"] == "remove" for revision in revisions)
            assert any(revision["operation"] == "restore" for revision in revisions)
            assert row["scope"] == "between_legs"
        assert any(
            row["payload"]["party"] == "Synthetic first client"
            and row["payload"]["note"] == "Synthetic offline correction"
            for row in retro
        )
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "correctedCalls": len(retro),
                    "projectionAuditVerified": True,
                    "checksums": dict(bundle.checksums),
                    "files": {
                        name: body.decode() for name, body in bundle.files.items()
                    },
                }
            )
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
