"""Inspect actual synthetic issue corrections through normal and audit projections."""

import json
import os
from pathlib import Path

from app.operator.projections import capture_projection
from store_probe import open_service


def main():
    service = open_service(Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"]))
    try:
        normal = capture_projection(service.store, mission_id="synthetic-mission-b")
        full = capture_projection(
            service.store, mission_id="synthetic-mission-b", include_audit=True
        )
        rows = [
            json.loads(line)
            for line in normal.files["operations/activity.jsonl"].splitlines()
        ]
        current = json.loads(normal.files["operations/current.json"])
        selected = [r for r in rows if r.get("issue_update", {}).get("is_selected")]
        corrected = [r for r in selected if r["issue_update"]["kind"] == "correction"]
        assert len(corrected) == 3
        for row in corrected:
            metadata = row["issue_update"]
            original = next(
                r for r in rows if r["identity"] == metadata["root_identity"]
            )
            assert original["issue_update"]["is_selected"] is False
            assert metadata["text"].startswith("Synthetic corrected backup")
            assert not any(
                name in row["changes"]
                for name in (
                    "payload.status",
                    "time.occurred_at",
                    "payload.follow_up_at",
                )
            )
            assert b"Synthetic original backup" in full.files["operations/audit.jsonl"]
        issues = [
            r
            for r in current
            if r["record_type"] == "issue"
            and r["payload"]["title"].startswith("Synthetic exception")
        ]
        assert len(issues) == 3 and all(
            r["payload"]["status"] == "reopened" for r in issues
        )
        assessments = [
            r for r in current if r["payload"]["entry_type"] == "capability_assessment"
        ]
        assert len(assessments) == 3
        assert all(
            r["payload"]["functional_status"] == "functional"
            and r["payload"]["redundancy_status"] == "unavailable"
            for r in assessments
        )
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "normalRevisionRows": len(rows),
                    "selectedCorrections": len(corrected),
                    "oneLogicalMessagePerRoot": True,
                    "manualAssessmentsIndependent": True,
                    "auditRetained": True,
                }
            )
        )
    finally:
        service.store.close()


if __name__ == "__main__":
    main()
