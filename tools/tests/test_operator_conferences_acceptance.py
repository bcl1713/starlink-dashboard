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
