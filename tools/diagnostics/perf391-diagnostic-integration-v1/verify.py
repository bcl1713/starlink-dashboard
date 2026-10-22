"""Export and hash offline Stage 1 identity evidence. Never builds or starts apps."""

import argparse
import json
from pathlib import Path

import build


def verify(repo, output):
    output = Path(output)
    build.require(not output.exists(), "evidence output must be new and isolated")
    output.mkdir(parents=True)
    report = {
        "schema": build.SCHEMA,
        "stage": 1,
        "pins": build.PINS,
        "roles": {},
        "equivalence": build.verify_equivalence(repo),
        "collector_release": build.verify_collector_release(repo),
        "image_built": False,
        "runtime_executed": False,
    }
    for role in ("A", "C"):
        root = output / role
        result = build.export_source(repo, role, build.PINS[role], root)
        raw = build.git(repo, "archive", "--format=tar", build.PINS[role])
        build.require(
            root.with_suffix(".tar").read_bytes() == raw, "archive bytes differ"
        )
        build.verify_primary(root)
        inventory_path = output / (role + "-files.json")
        inventory_path.write_bytes(build.canonical(result["files"]) + b"\n")
        report["roles"][role] = {k: v for k, v in result.items() if k != "files"}
        report["roles"][role].update(
            {
                "file_count": len(result["files"]),
                "inventory_sha256": build.digest(inventory_path.read_bytes()),
                "archive_byte_identical": True,
            }
        )
    report["dependencies"] = {}
    for kind in ("collector", "harness"):
        files = build.reference_files(repo, kind)
        build.verify_dependency(repo, kind, build.PINS[kind], files)
        inventory_path = output / (kind + "-files.json")
        inventory_path.write_bytes(build.canonical(files) + b"\n")
        report["dependencies"][kind] = {
            "sha": build.PINS[kind],
            "files": len(files),
            "inventory_sha256": build.digest(inventory_path.read_bytes()),
        }
    (output / "identity.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, args.output), indent=2))
