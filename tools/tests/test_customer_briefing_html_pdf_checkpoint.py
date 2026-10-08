import importlib.util
import json
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/acceptance/customer-briefing/html_pdf_checkpoint.py"


def module():
    assert MODULE.exists(), "atomic checkpoint publication contract absent"
    spec = importlib.util.spec_from_file_location("html_pdf_checkpoint", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def staging(tmp_path):
    p = tmp_path / "staging"
    p.mkdir()
    artifacts = {
        k: f"mission-customer-briefing-trial.{suffix}"
        for k, suffix in [("htmlPath", "html"), ("pngPath", "png"), ("pdfPath", "pdf")]
    }
    for name in artifacts.values():
        (p / name).write_bytes(b"validated fixture bytes")
    return (
        p,
        json.dumps(
            {
                "render": {
                    "status": "success",
                    "cleanup": {"success": True},
                    "pdfValidation": {"verified": True, "pageCount": 1},
                    "artifacts": artifacts,
                    "artifactHashes": {
                        k: sha256((p / name).read_bytes()).hexdigest()
                        for k, name in artifacts.items()
                    },
                }
            }
        ).encode(),
    )


def test_checkpoint_publishes_only_validated_pair(tmp_path):
    mod = module()
    p, e = staging(tmp_path)
    dest = tmp_path / "published"
    mod.publish_checkpoint(p, dest, e)
    assert sorted(x.suffix for x in dest.iterdir()) == [
        ".html",
        ".json",
        ".pdf",
        ".png",
    ]
    assert not p.exists()


def test_evidence_failure_after_pdf_leaves_no_deliverable(tmp_path):
    mod = module()
    p, e = staging(tmp_path)
    (p / "mission-customer-briefing-trial.pdf").write_bytes(b"changed")
    dest = tmp_path / "published"
    with pytest.raises(ValueError):
        mod.publish_checkpoint(p, dest, e)
    assert not dest.exists()


def test_cleanup_failure_rejects_publication(tmp_path):
    mod = module()
    p, e = staging(tmp_path)
    raw = json.loads(e)
    raw["render"]["cleanup"]["success"] = False
    dest = tmp_path / "published"
    with pytest.raises(ValueError):
        mod.publish_checkpoint(p, dest, json.dumps(raw).encode())
    assert not dest.exists()


def test_checkpoint_signal_cleans_owned_resources(tmp_path):
    mod = module()
    calls = []
    owner = mod.CheckpointOwner(
        "private-project",
        tmp_path,
        command=lambda args, **kwargs: calls.append(args) or "",
    )
    owner.signal(15, None)
    assert owner.cancelled
    owner.close()
    assert any("down" in c and "--volumes" in c for c in calls)
    assert owner.ownership["cleanup"]["children_reaped"]
    assert owner.ownership["cleanup"]["compose_removed"]


def test_outer_cleanup_failure_leaves_both_examples_unpublished(tmp_path):
    mod = module()
    pending = tmp_path / "deliverables-staging"
    pending.mkdir()
    for name in ("fully-assessed", "incomplete-x"):
        source, evidence = staging(pending)
        mod.publish_checkpoint(source, pending / name, evidence)

    class FailedOwner:
        def close(self):
            raise RuntimeError("Owned Docker resources remain")

    destination = tmp_path / "deliverables"
    with pytest.raises(RuntimeError, match="Owned Docker resources remain"):
        mod.publish_after_cleanup(FailedOwner(), pending, destination)
    assert not destination.exists()
    assert sorted(p.name for p in pending.iterdir()) == [
        "fully-assessed",
        "incomplete-x",
    ]


def test_outer_cleanup_precedes_atomic_pair_publication(tmp_path):
    mod = module()
    pending = tmp_path / "deliverables-staging"
    pending.mkdir()
    destination = tmp_path / "deliverables"

    class CleanOwner:
        def close(self):
            assert pending.exists() and not destination.exists()
            return {
                "children_reaped": True,
                "compose_removed": True,
                "remaining": {"containers": "", "networks": "", "volumes": ""},
            }

    mod.publish_after_cleanup(CleanOwner(), pending, destination)
    assert destination.exists() and not pending.exists()
