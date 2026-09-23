import json
import stat
from pathlib import Path

import pytest
from acceptance.artifacts import EvidenceWriter
from acceptance.model import RunManifest

SHA = "b" * 40


def test_writer_rejects_paths_outside_sha_root(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, "a" * 40)

    with pytest.raises(ValueError, match="outside"):
        writer.record_text(Path("../escape.txt"), "no")


def test_writer_records_json_with_restricted_modes(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, SHA)
    artifact = writer.record_json(Path("commands/result.json"), {"ok": True})

    assert json.loads(artifact.read_text(encoding="utf-8")) == {"ok": True}
    assert stat.S_IMODE(writer.sha_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(writer.artifact_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(artifact.stat().st_mode) == 0o600


def test_manifest_inventory_is_sorted_and_checksum_valid(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, SHA)
    writer.record_text(Path("z/result.txt"), "z")
    writer.record_text(Path("a/result.txt"), "a")

    manifest = writer.finalize_manifest(RunManifest.minimal(SHA, "feat/x"))

    assert [item["path"] for item in manifest["artifacts"]] == [
        "a/result.txt",
        "z/result.txt",
    ]
    assert (
        stat.S_IMODE((writer.artifact_root / "manifest.json").stat().st_mode) == 0o600
    )
    assert stat.S_IMODE((writer.artifact_root / "SHA256SUMS").stat().st_mode) == 0o600
    writer.verify_checksums()


def test_checksum_verification_detects_tampering(tmp_path: Path) -> None:
    writer = EvidenceWriter(tmp_path, SHA)
    artifact = writer.record_text(Path("result.txt"), "original")
    writer.finalize_manifest(RunManifest.minimal(SHA, "feat/x"))
    artifact.write_text("changed", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        writer.verify_checksums()


def test_writer_rejects_symlinked_artifact_parent_outside_evidence_root(
    tmp_path: Path,
) -> None:
    writer = EvidenceWriter(tmp_path, SHA)
    outside = tmp_path / "outside"
    outside.mkdir()
    (writer.artifact_root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        writer.record_text(Path("linked/escape.txt"), "no")

    assert not (outside / "escape.txt").exists()


def test_writer_rejects_preexisting_symlinked_sha_parent_during_construction(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(mode=0o755)
    (tmp_path / SHA).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="sha parent.*symlink"):
        EvidenceWriter(tmp_path, SHA)

    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert list(outside.iterdir()) == []


def test_writer_rejects_symlinked_sha_parent_outside_evidence_root(
    tmp_path: Path,
) -> None:
    writer = EvidenceWriter(tmp_path, SHA)
    outside = tmp_path / "outside"
    outside.mkdir()
    writer.artifact_root.rmdir()
    writer.sha_root.rmdir()
    writer.sha_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        writer.record_text(Path("escape.txt"), "no")

    assert not (outside / writer.artifact_root.name / "escape.txt").exists()
