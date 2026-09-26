import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess

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


def test_static_gate_rejects_a_missing_candidate_base(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_verify()
    monkeypatch.delenv("ACCEPTANCE_POLICY_BASE_SHA", raising=False)
    monkeypatch.setattr(module, "tier_commands", lambda _tier: [])

    assert module.main(["verify", "static"]) == 2



def test_added_type_ignore_uses_full_post_image_lexical_context() -> None:
    module = load_verify()
    diff = "\n".join(
        (
            "--- a/docs/example.md",
            "+++ b/docs/example.md",
            "@@ -0,0 +1 @@",
            "+" + "# type: ignore is documentation prose",
            "--- a/tools/tests/test_fixture.py",
            "+++ b/tools/tests/test_fixture.py",
            "@@ -0,0 +1,4 @@",
            "+fixture = \"\"\"",
            "+# type: ignore[arg-type]",
            "+\"\"\"",
            "+value = 1  # type: ignore[arg-type]",
            "--- a/tools/tests/test_policy.py",
            "+++ b/tools/tests/test_policy.py",
            "@@ -0,0 +1,2 @@",
            "+# ordinary comment boundary",
            "+value = 2  # type: ignore[assignment]",
        )
    )

    violations = module.added_type_ignore_violations(
        diff,
        {
            "tools/tests/test_fixture.py": (
                'fixture = """\n# type: ignore[arg-type]\n"""\n'
                "value = 1  # type: ignore[arg-type]\n"
            ),
            "tools/tests/test_policy.py": (
                "# ordinary comment boundary\n"
                "value = 2  # type: ignore[assignment]\n"
            ),
        },
    )

    assert violations == (
        "tools/tests/test_fixture.py:4: value = 1  # type: ignore[arg-type]",
        "tools/tests/test_policy.py:2: value = 2  # type: ignore[assignment]",
    )


def test_candidate_base_rejects_missing_invalid_noncommit_and_nonancestor_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = load_verify()
    repository = _repository_with_nonancestor_commit(tmp_path)
    monkeypatch.setattr(module, "ROOT", repository)

    monkeypatch.delenv("ACCEPTANCE_POLICY_BASE_SHA", raising=False)
    with pytest.raises(ValueError, match="required"):
        module.candidate_type_ignore_violations()

    monkeypatch.setenv("ACCEPTANCE_POLICY_BASE_SHA", "not-a-sha")
    with pytest.raises(ValueError, match="40-hex"):
        module.candidate_type_ignore_violations()

    blob = _git(repository, "hash-object", "-w", "--stdin", input="not a commit\n")
    monkeypatch.setenv("ACCEPTANCE_POLICY_BASE_SHA", blob)
    with pytest.raises(ValueError, match="commit"):
        module.candidate_type_ignore_violations()

    nonancestor = _git(repository, "rev-parse", "side")
    monkeypatch.setenv("ACCEPTANCE_POLICY_BASE_SHA", nonancestor)
    with pytest.raises(ValueError, match="ancestor"):
        module.candidate_type_ignore_violations()


def _repository_with_nonancestor_commit(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "policy@example.test")
    _git(repository, "config", "user.name", "Policy Test")
    (repository / "candidate.py").write_text("value = 1\n", encoding="utf-8")
    _git(repository, "add", "candidate.py")
    _git(repository, "commit", "-m", "base")
    _git(repository, "branch", "side")
    (repository / "candidate.py").write_text("value = 2\n", encoding="utf-8")
    _git(repository, "commit", "-am", "main")
    _git(repository, "switch", "side")
    (repository / "candidate.py").write_text("value = 3\n", encoding="utf-8")
    _git(repository, "commit", "-am", "side")
    _git(repository, "switch", "main")
    return repository


def _git(repository: Path, *arguments: str, input: str | None = None) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        input=input,
        text=True,
    ).stdout.strip()
