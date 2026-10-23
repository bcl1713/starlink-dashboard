"""Read-only, offline revalidation of retained receipts and artifact closure."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE / "evidence"
sys.path.insert(0, str(HERE.with_name("perf391-runtime-preparation-v1")))
import prepare
from launcher import validate_receipt

plan = json.loads((E / "runtime-build-plan.json").read_bytes())
qualification = json.loads((E / "qualification.json").read_bytes())
prepare.verify_overlay(plan)
assert prepare.check_release() == qualification["release"]
for role in ["A", "C"]:
    receipt_path = E / ("built-" + role + ".json")
    receipt = json.loads(receipt_path.read_bytes())
    validate_receipt(receipt, plan, prepare.sha(E / "runtime-build-plan.json"))
    assert prepare.sha(receipt_path) == qualification["roles"][role]["receipt_sha256"]
    assert (
        prepare.sha(E / (role + "-python-packages.json"))
        == "03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40"
    )
    assert (
        prepare.sha(E / (role + "-python-freeze.metadata-derived.txt"))
        == receipt["dependencies"]["python_freeze_sha256"]
    )
    assert (
        prepare.build.digest(
            prepare.build.canonical(
                {
                    "backend": prepare.sha(E / (role + "-backend-dpkg-status.txt")),
                    "frontend": prepare.sha(E / (role + "-frontend-apk-installed.txt")),
                }
            )
        )
        == receipt["dependencies"]["os_packages_sha256"]
    )
    for kind in ["backend", "frontend"]:
        image = json.loads((E / f"{role}-{kind}.image.json").read_bytes())[0]
        assert image["Id"] == receipt["images"][kind]["id"]
        assert image["Config"]["Labels"] == receipt["images"][kind]["labels"]
        assert image["RepoDigests"] == receipt["images"][kind]["repo_digests"]
        assert (E / f"{role}.{kind}.Dockerfile").read_bytes() == (
            prepare.HERE / "evidence/offline-final" / f"{role}.{kind}.Dockerfile"
        ).read_bytes()
cleanup = json.loads((E / "cleanup.json").read_bytes())
assert cleanup["cleanup_verified"] and not cleanup["task_process_survivors"]
assert not Path(cleanup["temporary_root_removed"]).exists()
assert all(not r["host_matches"] for r in cleanup["process_checks"])
if (HERE / "artifact-manifest.json").exists():
    manifest = json.loads((HERE / "artifact-manifest.json").read_bytes())
    actual = {
        p.relative_to(HERE).as_posix()
        for p in HERE.rglob("*")
        if p.is_file() and p != HERE / "artifact-manifest.json"
    }
    assert actual == set(manifest["files"]), "artifact file closure changed"
    for name, expected in manifest["files"].items():
        assert prepare.sha(HERE / name) == expected, name
print(
    "Both closed receipts, image/asset/dependency identities, approved recipes, frozen release and cleanup validate."
)
