"""Conference acceptance requires workflow and coverage-boundary evidence."""

import json
import pytest
from test_operator_journal_acceptance import implementation


def test_conference_proof_rejects_missing_source_boundary(tmp_path):
    runner = implementation()
    proof = {
        field: True
        for field in (
            "synthetic",
            "reuse",
            "overlap",
            "joiningOrders",
            "interruptRestore",
            "discrepancy",
            "twoClients",
            "retryFrozenTime",
            "retryConcurrentEdit",
            "restart",
        )
    }
    proof["captures"] = ["1920x1080", "390x844", "844x390"]
    (tmp_path / "conferences-proof.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="sourceCoverage"):
        runner.conferences_proof(tmp_path)
    proof["sourceCoverage"] = True
    (tmp_path / "conferences-proof.json").write_text(json.dumps(proof))
    assert runner.conferences_proof(tmp_path)["sourceCoverage"] is True


def test_conference_records_survive_real_multileg_lifecycle(tmp_path):
    import importlib
    import sys
    from pathlib import Path

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "backend/starlink-location")
    )
    implementation()
    result = importlib.import_module("export_probe").probe(tmp_path)
    assert result["conferenceLifecycleUnchanged"] is True
    assert result["telemetryZipSha256Before"] == result["telemetryZipSha256After"]
