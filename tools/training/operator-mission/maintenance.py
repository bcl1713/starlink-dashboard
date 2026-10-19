"""Run existing offline maintenance only in the marked private fixture clock."""

import argparse
import importlib.util
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def inspect_backup(root: Path, manifest: Path):
    """Read native validated artifacts; never restore or publish completion flags."""
    if os.getenv("OPERATOR_TRAINING_FIXTURE") != "explicit-private-training-v1":
        raise ValueError("Explicit private training fixture required")
    spec = importlib.util.spec_from_file_location(
        "operator_training_inspection_scenario", Path(__file__).with_name("scenario.py")
    )
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)
    namespace = scenario.training_namespace(root, mode="simulation")
    from app.operator.backup import checksum, validated_backup
    from app.operator.queries import select_records
    from app.operator.settings import OperatorSettings

    settings = OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode="simulation",
        simulation_run_id=namespace,
    )
    backups = settings.database_path.parent / "backups"
    manifest = manifest.resolve()
    if not manifest.is_relative_to(backups.resolve()):
        raise ValueError("Backup manifest must belong to this private Operator root")
    if manifest.stat().st_size > 64 * 1024:
        raise ValueError("Backup manifest exceeds private evidence limit")
    preliminary = json.loads(manifest.read_text())
    filename = preliminary.get("database")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError("Invalid native backup database path")
    database = manifest.parent / filename
    if (
        not database.resolve().is_relative_to(backups.resolve())
        or database.stat().st_size > 64 * 1024 * 1024
    ):
        raise ValueError("Backup exceeds private evidence boundary")
    info, database = validated_backup(manifest, clock=scenario.training_clock(root))
    if info["source_mode"] != "simulation" or info["simulation_run_id"] != namespace:
        raise ValueError("Backup belongs to another simulation namespace")
    identity = json.loads(settings.identity_path.read_text())
    if identity["store_id"] != info["store_id"]:
        raise ValueError("Backup belongs to another Operator store")
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    ) as connection:
        for table, limit in (("current_records", 1000), ("revisions", 5000)):
            if (
                connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                > limit
            ):
                raise ValueError("Backup exceeds private evidence row limit")
        records = select_records(
            connection, "SELECT * FROM current_records ORDER BY record_id"
        )
        history = select_records(
            connection, "SELECT * FROM revisions ORDER BY journal_seq"
        )
    report_path = settings.database_path.with_name("restore-report.json")
    report = json.loads(report_path.read_text()) if report_path.exists() else None
    preserved = None
    if report is not None:
        name = report["preserved"]
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Invalid native preserved store path")
        preserved_path = (
            settings.database_path.parent / name / settings.identity_path.name
        )
        if not preserved_path.resolve().is_relative_to(
            settings.database_path.parent.resolve()
        ):
            raise ValueError("Preserved identity outside private Operator root")
        preserved = json.loads(preserved_path.read_text())
    return {
        "manifest": info,
        "databaseSha256": checksum(database),
        "identity": identity,
        "records": [record.model_dump(mode="json") for record in records],
        "history": [record.model_dump(mode="json") for record in history],
        "restoreReport": report,
        "preservedIdentity": preserved,
    }


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
    parser.add_argument(
        "command", choices=("check", "backup", "restore", "inspect-backup")
    )
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.command == "inspect-backup":
        if args.manifest is None:
            parser.error("inspect-backup requires --manifest")
        print(json.dumps(inspect_backup(args.root, args.manifest), sort_keys=True))
    else:
        raise SystemExit(run(args.root, args.command, args.manifest))
