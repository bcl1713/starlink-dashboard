from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from acceptance.platform.model import Lane, RetentionDisposition, RetentionEntry
from acceptance.platform.retention import RetentionPolicy, canonical_root, safe_relative


def test_policy_is_exact(tmp_path: Path) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\n"
        "completed_generations_per_lane = 3\n"
        "maintenance_report_count = 90\n"
    )

    policy = RetentionPolicy.parse(policy_path)

    assert policy.version == 1
    assert policy.completed_generations_per_lane == 3
    assert policy.maintenance_report_count == 90
    assert len(policy.digest) == 64


@pytest.mark.parametrize("count", [2, 4, "3"])
def test_policy_rejects_nonfixed_completed_generation_count(
    tmp_path: Path, count: object
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(
        "version = 1\n"
        f"completed_generations_per_lane = {count!r}\n"
        "maintenance_report_count = 90\n"
    )

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("version", "true"),
        ("version", "1.0"),
        ("completed_generations_per_lane", "true"),
        ("completed_generations_per_lane", "3.0"),
        ("maintenance_report_count", "true"),
        ("maintenance_report_count", "90.0"),
    ],
)
def test_policy_rejects_type_confused_fixed_values(
    tmp_path: Path, key: str, value: str
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    values = {
        "version": "1",
        "completed_generations_per_lane": "3",
        "maintenance_report_count": "90",
    }
    values[key] = value
    policy_path.write_text("".join(f"{name} = {number}\n" for name, number in values.items()))

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


@pytest.mark.parametrize(
    "content",
    [
        "version = 2\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n",
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 91\n",
        "version = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\nextra = true\n",
        "version = 1\nversion = 1\ncompleted_generations_per_lane = 3\nmaintenance_report_count = 90\n",
    ],
)
def test_policy_rejects_any_value_or_key_outside_fixed_contract(
    tmp_path: Path, content: str
) -> None:
    policy_path = tmp_path / "retention-policy.toml"
    policy_path.write_text(content)

    with pytest.raises(ValueError):
        RetentionPolicy.parse(policy_path)


def test_retention_entry_is_an_immutable_classification_record() -> None:
    entry = RetentionEntry(
        path=PurePosixPath("final") / ("a" * 40),
        lane=Lane.FINAL,
        sha="a" * 40,
        disposition=RetentionDisposition.RETAIN,
        reason="protected final authority",
        byte_size=42,
    )

    assert entry.disposition is RetentionDisposition.RETAIN
    with pytest.raises(AttributeError):
        entry.reason = "mutated"  # type: ignore[misc]


def test_safe_relative_returns_posix_path_within_descriptor_confined_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    candidate = root / "final" / ("a" * 40)
    candidate.parent.mkdir(parents=True)

    relative = safe_relative(canonical_root(root), candidate)

    assert relative == PurePosixPath("final") / ("a" * 40)


def test_safe_relative_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path)

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root / "escape" / "x")


def test_safe_relative_rejects_lexical_escape(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root / ".." / "outside")


def test_safe_relative_rejects_retention_root_itself(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()

    with pytest.raises(ValueError):
        safe_relative(canonical_root(root), root)


def test_canonical_root_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root)

    with pytest.raises(ValueError):
        canonical_root(alias)


def test_canonical_root_normalizes_lexical_components_without_resolving(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir()

    assert canonical_root(root / ".." / "state") == root
