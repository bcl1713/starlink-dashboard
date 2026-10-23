"""Three-layer preflight identity; historical receipts and global guards stay closed."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREP = HERE.with_name("perf391-runtime-preparation-v1")
BUILT = HERE.with_name("perf391-built-images-v1")
LOGGING = HERE.with_name("perf391-logging-compat-v1")
sys.path.insert(0, str(PREP))
import prepare

ORIGINAL = "68f3f644beef98cd8412e8a354c8621540660739"
PLAN_SHA256 = "8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5"
CHECKPOINT_SHA256 = "16f96d3e1c40cc81e776b657014067e8c3319cf6c71dbf211fdecdec7f8bbe5f"
CONFIG_SHA256 = "63e98db136e5595cc6c0c1243382b2b8ccb7bc05445f508b7dc30a9fc52401c2"


NETWORK_SHA256 = "fdbbc561f690f1dfb7d7c0dd65c476b60df8e6da9f8879fbca8a07ad89ebba15"


def approved_correction():
    manifest_path = LOGGING / "artifact-manifest.json"
    # Distinct approved checkpoint input, independent of the original build plan.
    prepare.build.require(
        prepare.sha(manifest_path) == CHECKPOINT_SHA256,
        "logging checkpoint manifest identity",
    )
    manifest = json.loads(manifest_path.read_bytes())
    path = LOGGING / "evidence/config-hashes.json"
    prepare.build.require(
        prepare.sha(path)
        == CONFIG_SHA256
        == manifest["files"]["evidence/config-hashes.json"],
        "approved logging hashes identity",
    )
    approved = json.loads(path.read_bytes())
    prepare.build.require(
        prepare.sha(PREP / "node-contract-overlay.json")
        == approved["overlay_manifest_sha256"],
        "approved overlay manifest identity",
    )
    from runtime_identity import verify_runtime_overlay

    network_path = PREP / "network-overlay.json"
    prepare.build.require(prepare.sha(network_path) == NETWORK_SHA256, "network correction identity")
    network = json.loads(network_path.read_bytes())
    prepare.build.require(
        network["replaces"]["prepare.py"] == approved["prepare_py_sha256"],
        "approved predecessor compiler identity",
    )
    verify_runtime_overlay(json.loads((BUILT / "evidence/runtime-build-plan.json").read_bytes()))
    for role in ("A", "C"):
        prepare.build.require(
            prepare.sha(LOGGING / f"evidence/{role}.compose.json")
            == approved["roles"][role]["rendered_config_sha256"]
            == manifest["files"][f"evidence/{role}.compose.json"],
            "approved rendered configuration identity: " + role,
        )
    return approved, {
        "checkpoint_manifest_sha256": CHECKPOINT_SHA256,
        "config_hashes_sha256": CONFIG_SHA256,
        "overlay_manifest_sha256": approved["overlay_manifest_sha256"],
        "compiler_sha256": approved["prepare_py_sha256"],
        "network_manifest_sha256": NETWORK_SHA256,
        "network_compiler_sha256": network["files"]["prepare.py"],
    }


def compare(generated, original, overrides=None, bases=None):
    approved, provenance = approved_correction()
    expected = copy.deepcopy(original)
    differences = []
    network = json.loads((PREP / "network-overlay.json").read_bytes())
    for role in ("A", "C"):
        base = (bases or {r: prepare.compose(r)[0] for r in ("A", "C")})[role]
        digest = prepare.build.digest((json.dumps(base, sort_keys=True, indent=2) + "\n").encode())
        prepare.build.require(
            original["roles"][role]["compose_sha256"]["base"] == network["compose_base"]["original_sha256"]
            and digest == network["compose_base"]["corrected_sha256"],
            "approved network base identity: " + role,
        )
        expected["roles"][role]["compose_sha256"]["base"] = digest
        differences.append({
            "path": f"/roles/{role}/compose_sha256/base",
            "original": original["roles"][role]["compose_sha256"]["base"],
            "approved": digest,
        })
        override = (overrides or {r: prepare.compose(r)[1] for r in ("A", "C")})[role]
        prepare.build.require(
            prepare.build.digest(prepare.build.canonical(override))
            == approved["roles"][role]["compose_override_sha256"],
            "approved corrected override identity: " + role,
        )
        digest = prepare.build.digest(
            (json.dumps(override, sort_keys=True, indent=2) + "\n").encode()
        )
        expected["roles"][role]["compose_sha256"]["override"] = digest
        differences.append(
            {
                "path": f"/roles/{role}/compose_sha256/override",
                "original": original["roles"][role]["compose_sha256"]["override"],
                "approved": digest,
                "approved_canonical": approved["roles"][role][
                    "compose_override_sha256"
                ],
            }
        )
    prepare.build.require(
        generated == expected, "unexpected regenerated build-plan difference"
    )
    return {
        "original_fields_identical": True,
        "approved_override_hashes_match": True,
        "differences": differences,
        "correction": provenance,
    }


def regenerate(task):
    """Execute verified historical compiler, then apply approved logging/network deltas.

    No imported module paths are patched. The original compiler's output must first
    match the closed plan byte for byte; corrected hashes come only from real files.
    """
    plan_path = BUILT / "evidence/runtime-build-plan.json"
    prepare.build.require(
        prepare.sha(plan_path) == PLAN_SHA256, "immutable original plan"
    )
    original = json.loads(plan_path.read_bytes())
    from runtime_identity import verify_runtime_overlay

    verify_runtime_overlay(original)
    approved_correction()
    snapshot = task / "historical-source"
    snapshot.mkdir()
    archive = task / "historical.tar"
    with archive.open("wb") as out:
        subprocess.run(
            ["git", "-C", str(REPO), "archive", ORIGINAL, "tools"],
            stdout=out,
            check=True,
            timeout=30,
        )
    with tarfile.open(archive) as source:
        source.extractall(snapshot, filter="data")
    archive.unlink()
    # Git reads are against the real object database; source paths remain native.
    (snapshot / ".git").write_text(
        "gitdir: "
        + subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "--absolute-git-dir"], text=True
        ).strip()
        + "\n"
    )
    compiler = snapshot / PREP.relative_to(REPO) / "prepare.py"
    historical = compiler.parent
    for name, digest in original["overlay_files"].items():
        prepare.build.require(
            prepare.sha(historical / name) == digest,
            "historical compiler input: " + name,
        )
    context = task / "context"
    subprocess.run(
        [sys.executable, "-B", str(compiler), "--output", str(context)],
        check=True,
        timeout=120,
    )
    prepare.build.require(
        (context / "runtime-build-plan.json").read_bytes() == plan_path.read_bytes(),
        "original compiler regeneration",
    )
    generated = json.loads((context / "runtime-build-plan.json").read_bytes())
    overrides = {}
    bases = {}
    for role in ("A", "C"):
        bases[role], overrides[role] = prepare.compose(role)
        historical_base = json.loads((context / f"{role}.compose.base.json").read_bytes())
        expected_base = copy.deepcopy(historical_base)
        prepare.build.require(expected_base["networks"]["default"]["internal"] is True, "historical internal network")
        expected_base["networks"]["default"]["internal"] = False
        prepare.build.require(
            bases[role] == expected_base,
            "only approved internal network delta",
        )
        base_path = context / f"{role}.compose.base.json"
        prepare.write(base_path, bases[role])
        generated["roles"][role]["compose_sha256"]["base"] = prepare.sha(base_path)
        path = context / f"{role}.compose.override.json"
        prepare.write(path, overrides[role])
        generated["roles"][role]["compose_sha256"]["override"] = prepare.sha(path)
    comparison = compare(generated, original, overrides, bases)
    prepare.write(context / "runtime-build-plan.json", generated)
    return generated, comparison


def validate_compose(role, context, comparison):
    """Render only; compare the pinned effective config plus the approved network delta."""
    from launcher import launch_plan

    approved_correction()
    original_plan = context / "original-build-plan.json"
    original_plan.write_bytes((BUILT / "evidence/runtime-build-plan.json").read_bytes())
    prepare.build.require(
        prepare.sha(original_plan) == PLAN_SHA256, "closed receipt plan binding"
    )
    receipt = json.loads((BUILT / f"evidence/built-{role}.json").read_bytes())
    launch = launch_plan(
        role,
        "/tmp/perf391-smoke-408-" + role.lower(),
        original_plan,
        receipt,
    )
    launch["preflight_comparison"] = comparison
    launch["ownership"]["logging_correction"] = comparison["correction"]
    files = []
    for kind in ("base", "override"):
        path = context / f"{role}.compose.{kind}.json"
        files.extend(["-f", str(path)])
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "perf391-preflight-contract",
            *files,
            "config",
            "--format",
            "json",
        ],
        env={**os.environ, **launch["env"]},
        capture_output=True,
        check=True,
        timeout=20,
    )
    rendered = json.loads(result.stdout)
    approved = json.loads((LOGGING / f"evidence/{role}.compose.json").read_bytes())
    # Compose omits the false default. No other network or service field may differ.
    prepare.build.require(approved["networks"]["default"].pop("internal") is True, "approved historical internal network")
    prepare.build.require(rendered["networks"]["default"].get("internal", False) is False, "corrected non-internal network")
    # Compose resolves only this explicitly supplied context path differently.
    expected_context = launch["env"]["PERF391_CONTEXT"]
    for volume in approved["services"]["prometheus"]["volumes"]:
        if volume["target"] in (
            "/etc/prometheus/prometheus.yml",
            "/etc/prometheus/rules",
        ):
            relative = "monitoring/prometheus/" + (
                "prometheus.yml" if volume["target"].endswith(".yml") else "rules"
            )
            volume["source"] = str(Path(expected_context) / relative)
    # The project name is a deliberate offline validation namespace.
    old_project = approved["name"]
    approved["name"] = "perf391-preflight-contract"
    for group in ("networks", "volumes"):
        for value in approved.get(group, {}).values():
            if value.get("name", "").startswith(old_project + "_"):
                value["name"] = (
                    "perf391-preflight-contract" + value["name"][len(old_project) :]
                )
    prepare.build.require(
        rendered == approved, "effective approved Compose configuration: " + role
    )
    return launch, rendered
