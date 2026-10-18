"""Issue acceptance must prove corrections, durable drafts and snapshot boundaries."""

import json

import pytest
from test_operator_journal_acceptance import implementation

FIELDS = (
    "synthetic",
    "descriptionOnly",
    "workaroundMonitoring",
    "independentCapability",
    "snapshotBoundaries",
    "resolvedCorrection",
    "correctionLineage",
    "twoClients",
    "reloadFrozenRetry",
    "epochQuarantine",
    "restart",
    "multileg",
    "noReadinessInference",
)


def test_issue_proof_rejects_missing_failure_and_lineage(tmp_path):
    runner = implementation()
    proof = {field: True for field in FIELDS}
    proof["captures"] = ["1920x1080", "390x844", "844x390"]
    del proof["reloadFrozenRetry"]
    path = tmp_path / "issues-proof.json"
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="reloadFrozenRetry"):
        runner.issues_proof(tmp_path)
    proof["reloadFrozenRetry"] = True
    path.write_text(json.dumps(proof))
    assert runner.issues_proof(tmp_path)["resolvedCorrection"] is True


def test_issue_records_survive_real_multileg_lifecycle(tmp_path):
    import importlib
    import sys
    from pathlib import Path

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "backend/starlink-location")
    )
    implementation()
    result = importlib.import_module("export_probe").probe(tmp_path)
    assert result["issueCapabilityLifecycleUnchanged"] is True
    assert result["telemetryZipSha256Before"] == result["telemetryZipSha256After"]
