"""Inspect actual conference/customer revisions and unchanged lifecycle/export contracts."""

import json
import os
from pathlib import Path
from app.operator.projections import capture_projection
from store_probe import open_service


def main():
    service = open_service(Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"]))
    try:
        bundle = capture_projection(
            service.store, mission_id="synthetic-mission-a", include_audit=True
        )
        current = json.loads(bundle.files["operations/current.json"])
        audit = [
            json.loads(line)
            for line in bundle.files["operations/audit.jsonl"].splitlines()
        ]
        conferences = [
            r
            for r in current
            if r["record_type"] == "conference"
            and r["payload"]["title"].startswith("Synthetic conference ")
        ]
        assert len(conferences) == 3
        assert all(r["payload"]["status"] == "closed" for r in conferences)
        resumed = [
            r
            for r in current
            if r["record_type"] == "participation"
            and r["payload"].get("resumes_participation_id")
        ]
        assert len(resumed) == 3
        for record in resumed:
            predecessor = next(
                r
                for r in current
                if r["record_id"] == record["payload"]["resumes_participation_id"]
            )
            assert predecessor["payload"]["state"] == "interrupted"
            assert record["record_id"] != predecessor["record_id"]
            assert record["payload"]["state"] == "connected"
        assert any(r.get("reason") == "Customer connection restored" for r in audit)
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "conferences": len(conferences),
                    "resumedIntervals": len(resumed),
                    "immutableAudit": True,
                }
            )
        )
    finally:
        service.store.close()


if __name__ == "__main__":
    main()
