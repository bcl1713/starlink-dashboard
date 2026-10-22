"""Export guarded offline Stage 2 derivatives and inventories; never build/run."""

import argparse
import json
import shutil
from pathlib import Path

import build

PACKAGE = Path(__file__).resolve().parent
START = "a4e707e96226400051bbd05e28d831d8fbae6899"


def verify(repo, output):
    output = Path(output)
    build.require(not output.exists(), "evidence output must be new")
    output.mkdir(parents=True)
    specs = {
        role: json.loads((PACKAGE / "patches" / f"{role}.json").read_text())
        for role in ("A", "C")
    }
    build.verify_frontend_patch_agreement(specs["A"], specs["C"])
    report = {
        "stage": 2,
        "starting_commit": START,
        "ancestry_base": build.PINS["base"],
        "pins": build.PINS,
        "roles": {},
        "image_built": False,
        "application_started": False,
        "performance_measured": False,
        "equivalence": build.verify_equivalence(repo),
        "collector_release": build.verify_collector_release(repo),
    }
    for kind in ("collector", "harness"):
        inventory = build.reference_files(repo, kind)
        build.verify_dependency(repo, kind, build.PINS[kind], inventory)
        (output / f"{kind}-files.json").write_bytes(build.canonical(inventory) + b"\n")
    for role in ("A", "C"):
        control = output / role
        base = build.export_source(repo, role, build.PINS[role], control)
        build.verify_primary(control)
        derivative = output / (role + "-effective")
        shutil.copytree(control, derivative)
        patch = (PACKAGE / "patches" / f"{role}.patch").read_bytes()
        effective = build.apply_patch(derivative, patch, specs[role])
        for name in specs[role]["files"]:
            build.require(
                name == "backend/starlink-location/main.py"
                or name.startswith("backend/starlink-location/app/"),
                "Stage 2 backend-only patch required",
            )
            compile((derivative / name).read_bytes(), name, "exec")
        for name, record in base["files"].items():
            if name not in specs[role]["files"]:
                build.require(
                    effective["files"][name] == record,
                    "protected/non-target file changed",
                )
        inventory_path = output / (role + "-effective-files.json")
        inventory_path.write_text(json.dumps(effective["files"], indent=2) + "\n")
        report["roles"][role] = {
            "base_application_sha": build.PINS[role],
            "archive_sha256": base["archive_sha256"],
            "base_tree_sha256": base["tree_sha256"],
            "patch_sha256": build.digest(patch),
            "patch_spec_sha256": build.digest(
                (PACKAGE / "patches" / f"{role}.json").read_bytes()
            ),
            "effective_source_sha256": effective["tree_sha256"],
            "file_count": len(effective["files"]),
            "changed_files": sorted(specs[role]["files"]),
            "inventory_sha256": build.digest(inventory_path.read_bytes()),
        }
    report["modules"] = {
        name: build.digest((PACKAGE / name).read_bytes())
        for name in (
            "backend_probe.py",
            "workers.py",
            "contract.json",
            "integration-event-schema.json",
            "build.py",
            "contract.py",
        )
    }
    (output / "identity.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PACKAGE.parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, args.output), indent=2))
