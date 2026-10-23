"""Read-only qualification: no image build, container, application or browser."""

import argparse
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PREP = HERE.with_name("perf391-runtime-preparation-v1")
BUILT = HERE.with_name("perf391-built-images-v1")
sys.path.insert(0, str(PREP))
import prepare
from launcher import launch_plan
from runtime_identity import verify_runtime_overlay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--go", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # The original plan/receipts and all historical evidence stay closed.
    with patch.object(prepare, "verify_overlay", verify_runtime_overlay):
        runpy.run_path(str(BUILT / "verify-retained.py"), run_name="__offline_audit__")
    runpy.run_path(
        str(HERE.with_name("perf391-a-runtime-smoke-v1") / "verify.py"),
        run_name="__offline_audit__",
    )
    plan = BUILT / "evidence/runtime-build-plan.json"
    hashes = {
        "overlay_manifest_sha256": prepare.sha(PREP / "node-contract-overlay.json"),
        "corrected_overlay_sha256": prepare.build.digest(
            prepare.build.canonical(
                json.loads((PREP / "node-contract-overlay.json").read_bytes())[
                    "corrected_overlay_files"
                ]
            )
        ),
        "prepare_py_sha256": prepare.sha(PREP / "prepare.py"),
        "roles": {},
    }
    with tempfile.TemporaryDirectory(prefix="perf391-logging-check-") as tmp:
        root = Path(tmp)
        for role in ("A", "C"):
            receipt = json.loads((BUILT / f"evidence/built-{role}.json").read_bytes())
            proposal = launch_plan(
                role, "/tmp/perf391-smoke-408-" + role.lower(), plan, receipt
            )
            files = []
            for kind in ("base", "override"):
                path = root / f"{role}.{kind}.json"
                prepare.write(path, proposal["compose"][kind])
                files.extend(["-f", str(path)])
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    "perf391-logging-fix",
                    *files,
                    "config",
                    "--format",
                    "json",
                ],
                env={**os.environ, **proposal["env"]},
                check=True,
                capture_output=True,
                timeout=20,
            )
            rendered = args.output / f"{role}.compose.json"
            prepare.write(rendered, json.loads(result.stdout))
            hashes["roles"][role] = {
                "compose_base_sha256": prepare.build.digest(
                    prepare.build.canonical(proposal["compose"]["base"])
                ),
                "compose_override_sha256": prepare.build.digest(
                    prepare.build.canonical(proposal["compose"]["override"])
                ),
                "rendered_config_sha256": prepare.sha(rendered),
            }
        # Run the unmodified Docker config.go with its exact pinned dependencies.
        shutil.copyfile(HERE / "upstream/config.go", root / "config.go")
        shutil.copyfile(HERE / "logging_test.go", root / "logging_test.go")
        for name in ("go.mod", "go.sum"):
            shutil.copyfile(HERE / name, root / name)
        source = (HERE / "upstream/local.go").read_text()
        constants = []
        for name in (
            "defaultMaxFileSize",
            "defaultMaxFileCount",
            "defaultCompressLogs",
        ):
            match = re.search(r"^\s*" + name + r"\s+[^\n]+", source, re.M)
            assert match, name
            constants.append(match.group().strip())
        (root / "defaults.go").write_text(
            "package local\nconst (\n" + "\n".join(constants) + "\n)\n"
        )
        subprocess.run(
            [args.go, "test", "-count=1", "-timeout=30s", "-v", "."],
            cwd=root,
            env={
                **os.environ,
                "GOPROXY": "off",
                "GOSUMDB": "off",
                "PERF391_LOGGING_CONFIGS": str(args.output.resolve()),
            },
            check=True,
            timeout=60,
        )
    prepare.write(args.output / "config-hashes.json", hashes)


if __name__ == "__main__":
    main()
