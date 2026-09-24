from dataclasses import FrozenInstanceError

import pytest
from acceptance.platform.model import (
    BuildLedgerKey,
    Lane,
    Outcome,
    RunResult,
    validate_candidate_inputs,
)

SHA = "a" * 40


def test_static_result_cannot_claim_final_acceptance() -> None:
    with pytest.raises(ValueError, match="final"):
        RunResult(lane=Lane.STATIC, outcome=Outcome.PASSED, final=True).validate()


def test_final_result_requires_passed_outcome() -> None:
    with pytest.raises(ValueError, match="passed"):
        RunResult(lane=Lane.FINAL, outcome=Outcome.FAILED, final=True).validate()


def test_candidate_inputs_preserve_full_sha_and_ref_literally() -> None:
    sha, ref = validate_candidate_inputs(SHA, "refs/heads/feat/acceptance")

    assert sha == SHA
    assert ref == "refs/heads/feat/acceptance"


@pytest.mark.parametrize(
    ("sha", "ref"),
    [
        ("a" * 39, "refs/heads/feat/x"),
        ("A" * 40, "refs/heads/feat/x"),
        (f" {SHA}", "refs/heads/feat/x"),
        (SHA, " refs/heads/feat/x"),
        (SHA, "refs/heads/feat..bad"),
        (SHA, "refs/heads/topic./next"),
        (SHA, SHA),
    ],
)
def test_candidate_inputs_reject_abbreviated_or_normalized_values(
    sha: str, ref: str
) -> None:
    with pytest.raises(ValueError):
        validate_candidate_inputs(sha, ref)


def test_build_ledger_key_is_frozen() -> None:
    key = BuildLedgerKey(SHA, "b" * 64, "c" * 64)

    with pytest.raises(FrozenInstanceError):
        key.candidate_sha = "d" * 40  # type: ignore[misc]
