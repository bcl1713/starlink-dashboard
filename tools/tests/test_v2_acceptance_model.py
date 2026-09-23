from pathlib import Path

import pytest
from acceptance.model import (
    AcceptanceInputs,
    AcceptancePhase,
    PhaseResult,
    RunManifest,
)

SHA = "a" * 40


def test_inputs_require_full_sha_and_named_ref() -> None:
    with pytest.raises(ValueError, match="40-character"):
        AcceptanceInputs.from_mapping({"sha": "0437a0bb", "ref": "feat/x"})

    with pytest.raises(ValueError, match="named ref"):
        AcceptanceInputs.from_mapping(
            {"sha": SHA, "ref": SHA, "evidence_root": "/evidence"}
        )


def test_inputs_preserve_valid_values_and_default_to_full() -> None:
    inputs = AcceptanceInputs.from_mapping(
        {"sha": SHA, "ref": "feat/x", "evidence_root": "/evidence"}
    )

    assert inputs.sha == SHA
    assert inputs.ref == "feat/x"
    assert inputs.evidence_root == Path("/evidence")
    assert inputs.phase is AcceptancePhase.FULL


def test_inputs_reject_unknown_phase_without_normalizing_values() -> None:
    with pytest.raises(ValueError, match="phase"):
        AcceptanceInputs.from_mapping(
            {
                "sha": SHA,
                "ref": "feat/x",
                "evidence_root": "/evidence",
                "phase": " full ",
            }
        )


def test_runtime_cached_cannot_be_final_result() -> None:
    result = PhaseResult("runtime-cached", "passed", final_acceptance=True)

    with pytest.raises(ValueError, match="non-final"):
        result.validate()


def test_full_pass_can_be_final_and_manifest_preserves_outcomes() -> None:
    primary = PhaseResult("full", "passed", final_acceptance=True)
    cleanup = PhaseResult("full", "failed")
    manifest = RunManifest.minimal(SHA, "feat/x").with_outcomes(primary, cleanup)

    assert manifest.to_dict()["primary_status"] == "passed"
    assert manifest.to_dict()["cleanup_status"] == "failed"
    assert manifest.to_dict()["final_acceptance"] is True
