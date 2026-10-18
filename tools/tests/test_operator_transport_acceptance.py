"""Transport acceptance requires evidence from actual production interfaces."""

import json
import pytest
from test_operator_journal_acceptance import implementation


def test_transport_proof_requires_all_scenarios(tmp_path):
    implementation()
    from transport_qualification import FIELDS, transport_proof

    proof = {field: True for field in FIELDS}
    proof["captures"] = ["1920x1080", "390x844", "844x390"]
    proof.pop("lostReceipt")
    (tmp_path / "transport-proof.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="lostReceipt"):
        transport_proof(tmp_path)
    proof["lostReceipt"] = True
    (tmp_path / "transport-proof.json").write_text(json.dumps(proof))
    assert transport_proof(tmp_path)["unknownActualRouting"]


def test_transport_runner_selection_is_explicit():
    import inspect

    runner = implementation()
    assert "transport" in inspect.signature(runner.run).parameters


def test_transport_records_preserve_existing_export_contracts(tmp_path, monkeypatch):
    implementation()
    from app.mission import storage
    from export_probe import probe

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    result = probe(tmp_path / "export-controls")
    assert result["transportDecisionLifecycleUnchanged"]
    assert result["telemetryZipSha256Before"] == result["telemetryZipSha256After"]
    assert (
        result["planningCsvSemanticSha256Before"]
        == result["planningCsvSemanticSha256After"]
    )
