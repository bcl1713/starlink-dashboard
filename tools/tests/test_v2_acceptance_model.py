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


@pytest.mark.parametrize(
    "ref",
    [
        "refs/heads/feat..bad",
        "refs/heads/feat.",
        "refs/heads/feat@{bad",
        "refs/heads/feat\x01bad",
        "refs/heads/feat~bad",
        "refs/heads/feat^bad",
        "refs/heads/feat:bad",
        "refs/heads/feat?bad",
        "refs/heads/feat*bad",
        "refs/heads/feat[bad",
        "refs/heads/.hidden",
        "refs/heads/feat.lock",
    ],
)
def test_inputs_reject_git_invalid_refnames(ref: str) -> None:
    with pytest.raises(ValueError, match="named ref"):
        AcceptanceInputs.from_mapping(
            {"sha": SHA, "ref": ref, "evidence_root": "/evidence"}
        )


def test_runtime_cached_cannot_be_final_result() -> None:
    result = PhaseResult("runtime-cached", "passed", final_acceptance=True)

    with pytest.raises(ValueError, match="non-final"):
        result.validate()


def test_manifest_rejects_results_from_a_different_phase() -> None:
    manifest = RunManifest(SHA, "feat/x", AcceptancePhase.RUNTIME_CACHED)

    with pytest.raises(ValueError, match="manifest phase"):
        manifest.with_outcomes(
            PhaseResult("full", "passed", final_acceptance=True),
            PhaseResult("runtime-cached", "passed"),
        )


def test_cached_manifest_cannot_serialize_a_full_final_result() -> None:
    manifest = RunManifest(
        SHA,
        "feat/x",
        AcceptancePhase.RUNTIME_CACHED,
        primary_result=PhaseResult("full", "passed", final_acceptance=True),
    )

    with pytest.raises(ValueError, match="manifest phase"):
        manifest.to_dict()


def test_full_pass_can_be_final_and_manifest_preserves_outcomes() -> None:
    primary = PhaseResult("full", "passed", final_acceptance=True)
    cleanup = PhaseResult("full", "failed")
    manifest = RunManifest.minimal(SHA, "feat/x").with_outcomes(primary, cleanup)

    assert manifest.to_dict()["primary_status"] == "passed"
    assert manifest.to_dict()["cleanup_status"] == "failed"
    assert manifest.to_dict()["final_acceptance"] is True
