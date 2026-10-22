"""Offline Stage 3A exact A/C derivation. No image, network or app launch path."""

import argparse
import json
import shutil
from pathlib import Path
import build

PACKAGE = Path(__file__).resolve().parent
START = "e880c4d9e6b2b9c7c46bcf7985ab028efe98e5cd"
MODULES = ("browser-probe.ts", "browser.mjs", "frontend-config.mjs")


def verify(repo, output):
    output = Path(output)
    build.require(not output.exists(), "output must be new")
    specs = {
        r: json.loads((PACKAGE / "patches/frontend" / f"{r}.json").read_text())
        for r in ("A", "C")
    }
    build.verify_frontend_patch_agreement(specs["A"], specs["C"])
    patches = {
        r: (PACKAGE / "patches/frontend" / f"{r}.patch").read_bytes()
        for r in ("A", "C")
    }
    build.require(patches["A"] == patches["C"], "nonidentical frontend patches")
    output.mkdir(parents=True)
    report = {
        "stage": "3A",
        "starting_commit": START,
        "image_built": False,
        "application_started": False,
        "runtime_authorized": False,
        "roles": {},
        "modules": {
            name: build.digest((PACKAGE / name).read_bytes()) for name in MODULES
        },
        "equivalence": build.verify_equivalence(repo),
    }
    for role in ("A", "C"):
        control = output / (role + "-control")
        base = build.export_source(repo, role, build.PINS[role], control)
        build.verify_primary(control)
        effective = output / (role + "-effective")
        shutil.copytree(control, effective)
        backend_spec = json.loads((PACKAGE / "patches" / f"{role}.json").read_text())
        backend = build.apply_patch(
            effective,
            (PACKAGE / "patches" / f"{role}.patch").read_bytes(),
            backend_spec,
        )
        final = build.apply_patch(effective, patches[role], specs[role])
        for name in specs[role]["files"]:
            build.require(
                name.startswith("frontend/mission-planner/src/")
                and name.endswith((".ts", ".tsx")),
                "frontend-only Stage 3A patch",
            )
        for name, entry in backend["files"].items():
            if name not in specs[role]["files"]:
                build.require(
                    final["files"][name] == entry, "non-target source changed"
                )
        frontend = {
            name: entry
            for name, entry in final["files"].items()
            if name.startswith("frontend/")
        }
        (output / f"{role}-files.json").write_text(
            json.dumps(final["files"], indent=2) + "\n"
        )
        report["roles"][role] = {
            "base_application_sha": build.PINS[role],
            "archive_sha256": base["archive_sha256"],
            "stage2_effective_source_sha256": backend["tree_sha256"],
            "frontend_patch_sha256": build.digest(patches[role]),
            "frontend_spec_sha256": build.digest(
                (PACKAGE / "patches/frontend" / f"{role}.json").read_bytes()
            ),
            "effective_source_sha256": final["tree_sha256"],
            "frontend_tree_sha256": build.digest(build.canonical(frontend)),
            "frontend_closure_sha256": build.digest(
                build.canonical(
                    {"frontend": frontend, "external_modules": report["modules"]}
                )
            ),
            "frontend_files": specs[role]["files"],
            "projection_module_hashes": {
                name: entry["sha256"]
                for name, entry in frontend.items()
                if name.rsplit("/", 1)[-1]
                in (
                    "overview-metric-retention.ts",
                    "overview-metric-history.ts",
                    "overview-metric-plot-options.ts",
                    "overview-metric-scale.ts",
                    "overview-metric-motion.ts",
                    "OverviewMetricHistoryPanel.css",
                )
            },
            "inventory_sha256": build.digest(
                (output / f"{role}-files.json").read_bytes()
            ),
        }
    build.require(
        report["roles"]["A"]["frontend_tree_sha256"]
        == report["roles"]["C"]["frontend_tree_sha256"],
        "effective frontend differs",
    )
    (output / "identity.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PACKAGE.parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.repo, args.output), indent=2))
