"""Run existing offline maintenance only in the marked private fixture clock."""

import argparse
import importlib.util
import os
from pathlib import Path


def run(root: Path, command: str, manifest: Path | None = None):
    if os.getenv("OPERATOR_TRAINING_FIXTURE") != "explicit-private-training-v1":
        raise ValueError("Explicit private training fixture required")
    spec = importlib.util.spec_from_file_location(
        "operator_training_maintenance_scenario",
        Path(__file__).with_name("scenario.py"),
    )
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)
    namespace = scenario.training_namespace(root, mode="simulation")
    if command not in ("check", "backup", "restore"):
        raise ValueError(
            "Private training supports existing check, backup and restore only"
        )
    if command == "restore" and (
        manifest is None
        or not manifest.resolve().is_relative_to((root / "operator").resolve())
    ):
        raise ValueError("Restore manifest must belong to this private Operator root")
    from app.operator import __main__ as cli

    args = [
        command,
        "--root",
        str(root / "operator"),
        "--mode",
        "simulation",
        "--run",
        namespace,
    ]
    if manifest is not None:
        args.extend(["--manifest", str(manifest)])
    original_clock = cli.SystemClock
    try:
        clock = scenario.training_clock(root)
        cli.SystemClock = lambda: clock
        return cli.main(args)
    finally:
        cli.SystemClock = original_clock


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("command", choices=("check", "backup", "restore"))
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    raise SystemExit(run(args.root, args.command, args.manifest))
