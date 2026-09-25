import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).resolve().parents[2]
VERIFY = REPOSITORY / "tools/verify"


def load_verify():
    loader = importlib.machinery.SourceFileLoader("verify", str(VERIFY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_added_type_ignore_is_rejected() -> None:
    module = load_verify()

    violations = module.added_type_ignore_lines("+value = 1  # type: ignore[arg-type]\n")

    assert violations == ("value = 1  # type: ignore[arg-type]",)


def test_added_type_ignore_ignores_non_python_files_and_string_fixtures() -> None:
    module = load_verify()
    diff = "\n".join(
        (
            "--- a/docs/example.md",
            "+++ b/docs/example.md",
            "@@ -0,0 +1 @@",
            "+" + "# type: ignore is documentation prose",
            "--- a/tools/tests/test_fixture.py",
            "+++ b/tools/tests/test_fixture.py",
            "@@ -0,0 +1 @@",
            "+fixture = \"# type: ignore[arg-type]\"",
            "--- a/tools/tests/test_policy.py",
            "+++ b/tools/tests/test_policy.py",
            "@@ -0,0 +1 @@",
            "+value = 1  # type: ignore[arg-type]",
        )
    )

    violations = module.added_type_ignore_violations(diff)

    assert violations == ("tools/tests/test_policy.py:1: value = 1  # type: ignore[arg-type]",)


def test_candidate_base_rejects_every_added_type_ignore(monkeypatch: pytest.MonkeyPatch) -> None:
    base = os.environ.get("ACCEPTANCE_POLICY_BASE_SHA")
    if base is None:
        pytest.skip("ACCEPTANCE_POLICY_BASE_SHA is required for candidate policy verification")

    module = load_verify()
    monkeypatch.setenv("ACCEPTANCE_POLICY_BASE_SHA", base)

    assert module.candidate_type_ignore_violations() == ()
