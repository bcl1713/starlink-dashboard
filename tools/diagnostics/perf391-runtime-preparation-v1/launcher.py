"""Proposed launch-plan compiler. Default and only enabled mode is offline dry-run.

It emits argv, ownership and ordering for a future separately authorized executor.
It never executes these commands. --execute is an intentional hard gate at this
preparation checkpoint, not a claim of a qualified runtime runner.
"""

import argparse
import json
from pathlib import Path

from prepare import HERE, sha, compose, build
from runtime_identity import (
    validate_diagnostic_node,
    DIAGNOSTIC_NODE_VERSION,
    DIAGNOSTIC_NODE_SHA256,
    HISTORICAL_NODE_VERSION,
    HISTORICAL_NODE_SHA256,
)


def validate_receipt(receipt, plan, plan_hash):
    from jsonschema import Draft202012Validator

    schema = json.loads((HERE / "runtime-receipt-schema.json").read_bytes())
    Draft202012Validator(schema).validate(receipt)
    build.require(receipt["plan_sha256"] == plan_hash, "receipt plan identity")
    expected = plan["roles"][receipt["role"]]["labels"]
    for kind, image in receipt["images"].items():
        build.require(
            all(image["labels"].get(k) == v for k, v in expected.items()),
            "wrong image labels: " + kind,
        )
        build.require(image["id"] != "sha256:" + "0" * 64, "dry-run sentinel image")
    build.require(
        receipt["dependencies"]["npm_lock_sha256"]
        == plan["roles"][receipt["role"]]["package_lock_sha256"],
        "npm lock identity",
    )
    validate_diagnostic_node(receipt["browser"])
    assets = receipt["assets"]
    build.require(
        {"index.html", ".vite/manifest.json", "perf391-module-closure.json"}
        <= set(assets),
        "asset closure absent",
    )
    root = Path(receipt["asset_root"]).resolve()
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() or p.is_symlink()
    }
    build.require(actual == set(assets), "asset inventory differs")
    for name, expected_hash in assets.items():
        build.safe_path(name)
        path = root / name
        build.require(
            not path.is_symlink()
            and root in path.resolve().parents
            and sha(path) == expected_hash,
            "asset hash/path drift",
        )
    closure = json.loads((root / "perf391-module-closure.json").read_bytes())
    build.require(
        closure.get("schema") == "perf391-compiled-modules-v1",
        "compiled closure schema",
    )
    live = [
        m["id"]
        for rows in closure["modules"].values()
        for m in rows
        if m["renderedLength"] > 0
    ]
    for name in (
        "diagnostic/browser-runtime.ts",
        "diagnostic/browser-probe.ts",
        "src/hooks/api/useOverviewHistory.ts",
        "src/services/overview-history.ts",
        "src/pages/OverviewMetricHistoryPanel.tsx",
    ):
        build.require(
            any(m.endswith(name) for m in live),
            "missing compiled diagnostic module: " + name,
        )
    for chunk in closure["modules"]:
        build.require(chunk in assets, "compiled chunk absent from assets")
    manifest = json.loads((root / ".vite/manifest.json").read_bytes())
    for item in manifest.values():
        for name in [item["file"], *item.get("css", []), *item.get("assets", [])]:
            build.require(name in assets, "Vite asset reference absent")
        for name in [*item.get("imports", []), *item.get("dynamicImports", [])]:
            build.require(name in manifest, "Vite chunk reference absent")


def launch_plan(role, root, plan_path, receipt=None):
    build.require(role in ("A", "C"), "role")
    root = Path(root).absolute()
    build.require(
        str(root).startswith("/tmp/perf391-smoke-408-") and not root.exists(),
        "new task-owned runtime root required",
    )
    ports = (
        (38080, 38081, 38082, 38083) if role == "A" else (38180, 38181, 38182, 38183)
    )
    project = "perf391-smoke-408-" + role.lower()
    context = Path(plan_path).resolve().parent / role
    plan = json.loads(Path(plan_path).read_bytes())
    build.require(
        plan["runtime_authorized"] is False
        and plan["schema"] == "perf391-runtime-build-plan-v1",
        "preparation plan contract",
    )
    if receipt:
        validate_receipt(receipt, plan, sha(plan_path))
        build.require(receipt["role"] == role, "receipt role")
    images = (
        receipt["images"]
        if receipt
        else {k: {"id": "UNBUILT_" + k.upper()} for k in ("backend", "frontend")}
    )
    env = {
        "PERF391_RUN": "synthetic-408" + role.lower(),
        "PERF391_OUTPUT": str(root),
        "PERF391_CONTEXT": str(context),
        "PERF391_FRONTEND_PORT": str(ports[0]),
        "PERF391_BACKEND_PORT": str(ports[1]),
        "PERF391_PROMETHEUS_PORT": str(ports[2]),
        "PERF391_BACKEND_IMAGE": images["backend"]["id"],
        "PERF391_FRONTEND_IMAGE": images["frontend"]["id"],
    }
    dc = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(root / "compose.base.json"),
        "-f",
        str(root / "compose.override.json"),
    ]
    commands = [
        {
            "phase": "seed-file",
            "seconds": 3,
            "argv": [
                "python3",
                str(context / "tools/acceptance/overview_history/seed.py"),
                "--output",
                str(root / "history.openmetrics"),
                "--end",
                "FUTURE_UTC_SECONDS_MINUS_20",
            ],
        },
        {
            "phase": "seed-tsdb",
            "seconds": 7,
            "argv": [
                *dc,
                "run",
                "--rm",
                "--no-deps",
                "--name",
                project + "-seed",
                "--entrypoint",
                "/bin/promtool",
                "prometheus",
                "tsdb",
                "create-blocks-from",
                "openmetrics",
                "/seed/history.openmetrics",
                "/prometheus",
            ],
        },
        {
            "phase": "start-backend-prometheus",
            "seconds": 18,
            "argv": [
                *dc,
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never",
                "--wait",
                "--wait-timeout",
                "16",
                "prometheus",
                "starlink-location",
            ],
        },
        {
            "phase": "start-nginx",
            "seconds": 2,
            "argv": [
                *dc,
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never",
                "--no-deps",
                "mission-planner",
            ],
        },
        {
            "phase": "browser-and-source",
            "seconds": 35,
            "argv": [
                "REVIEWED_NODE_22_22_2",
                str(HERE / "browser-owner.proposed.mjs"),
                str(root / "browser-options.json"),
            ],
        },
        {
            "phase": "stop-backend",
            "seconds": 8,
            "argv": [*dc, "stop", "-t", "6", "starlink-location"],
        },
        {
            "phase": "copy-final-backend",
            "seconds": 3,
            "argv": [
                *dc,
                "cp",
                "starlink-location:/app/data/perf391/.",
                str(root / "backend"),
            ],
        },
        {
            "phase": "cleanup",
            "seconds": 10,
            "argv": [*dc, "down", "--volumes", "--remove-orphans", "--timeout", "2"],
        },
    ]
    base, override = compose(role)
    return {
        "schema": "perf391-proposed-launch-v1",
        "mode": "dry_run",
        "runtime_lane": {
            "purpose": "diagnostic functionality only; no historical timing comparison",
            "image_build_app_node_minimum": "22.22.2",
            "diagnostic_browser_node_version": DIAGNOSTIC_NODE_VERSION,
            "diagnostic_browser_node_sha256": DIAGNOSTIC_NODE_SHA256,
            "historical_frozen_browser_node_version": HISTORICAL_NODE_VERSION,
            "historical_frozen_browser_node_sha256": HISTORICAL_NODE_SHA256,
            "correction_manifest_sha256": sha(HERE / "node-contract-overlay.json"),
        },
        "runtime_authorized": False,
        "role": role,
        "root": str(root),
        "project": project,
        "env": env,
        "commands": commands,
        "compose": {"base": base, "override": override},
        "browser_options": {
            "run": env["PERF391_RUN"],
            "samples": 5,
            "output": str(root / "browser"),
            "origin": f"http://127.0.0.1:{ports[0]}",
            "source": f"http://127.0.0.1:{ports[1]}/api/_diagnostic/state",
            "browserPort": ports[3],
            "nodeRoot": (
                receipt["browser"]["playwright_root"]
                if receipt
                else "UNAVAILABLE_REVIEWED_PLAYWRIGHT_ROOT"
            ),
            "chromiumExecutable": (
                receipt["browser"]["chromium_executable"]
                if receipt
                else "UNAVAILABLE_REVIEWED_CHROMIUM"
            ),
        },
        "ownership": {
            "paths": [str(root)],
            "volumes": [project + "_" + n for n in ("data", "routes", "metrics")],
            "networks": [project + "_default"],
            "ports": list(ports),
            "intent_before_spawn": True,
            "pid_pgid_start_id_and_command_required": True,
            "docker_containers": [
                project + "-seed",
                project + "-starlink-location-1",
                project + "-mission-planner-1",
                project + "-prometheus-1",
            ],
        },
        "deadlines": {
            "work_seconds": 78,
            "cleanup_by_seconds": 90,
            "outer_timeout_seconds": 90,
            "kill_grace_seconds": 10,
        },
        "hard_gates": [
            "separate authorization",
            "built receipt",
            "Node engine floor",
            "free ports then exclusive task lock",
            "source/context/label/asset identity",
            "host PID/cgroup mapping",
            "zero loss and final summaries",
            "no skipped source deadline; unchanged 1.5s cadence",
            "no retry",
            "verified cleanup before C",
        ],
        "serial_phase_upper_bound_seconds": sum(c["seconds"] for c in commands),
        "note": "Phase caps share a 78s work deadline, not additive extensions. Always reserve cleanup until 90s. Offline analysis follows shutdown.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["A", "C"], required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute:
        parser.error(
            "STOP: preparation checkpoint only; runtime executor requires separate review and authorization"
        )
    receipt = json.loads(args.receipt.read_bytes()) if args.receipt else None
    print(
        json.dumps(
            launch_plan(args.role, args.root, args.plan, receipt),
            sort_keys=True,
            indent=2,
        )
    )
