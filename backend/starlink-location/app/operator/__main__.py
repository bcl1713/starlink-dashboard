"""Explicit local maintenance: python -m app.operator COMMAND --root --mode."""

import argparse
import json
from pathlib import Path

from .backup import backup_store
from .clock import SystemClock
from .errors import OperatorError
from .recovery import restore_store, verify_store
from .runtime import namespace_status
from .settings import OperatorSettings
from .store import OperatorStore


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline Operator administration; restore replaces the whole store."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("initialize", "check", "backup", "restore", "upgrade", "export"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--mode", choices=("live", "simulation"), required=True)
        command.add_argument(
            "--run", help="Simulation run ID, or evaluation name with --mission-journal"
        )
        command.add_argument(
            "--mission-journal",
            action="store_true",
            help="Use normal simulation mission journals, never a legacy run store",
        )
        if name == "export":
            command.add_argument("--mission", required=True)
            command.add_argument("--output", type=Path, required=True)
        if name == "backup":
            command.add_argument("--directory", type=Path)
        if name == "restore":
            command.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    store = None
    try:
        settings = OperatorSettings(
            enabled=True,
            root=args.root,
            source_mode=args.mode,
            simulation_run_id=args.run,
            mission_journal=args.mission_journal,
        )
        clock = SystemClock()
        if args.command == "upgrade":
            from .upgrade import upgrade_store

            result = {
                "upgraded": True,
                "backup_manifest": str(upgrade_store(settings, clock=clock)),
            }
        elif args.command == "restore":
            health = restore_store(settings, manifest=args.manifest, clock=clock)
            result = health.model_dump(mode="json")
        else:
            status = (
                namespace_status(settings) if args.command == "initialize" else None
            )
            if status == "recovery":
                raise OperatorError("store_recovery_required")
            store = OperatorStore.open(
                settings, initialize=status == "new", clock=clock
            )
            if args.command == "export":
                from zipfile import ZIP_DEFLATED, ZipFile

                from app.mission.package.operations_archive import journal_files

                from .projections import capture_projection

                bundle = capture_projection(
                    store,
                    mission_id=args.mission,
                    include_audit=True,
                    include_events=True,
                    max_input_bytes=128 * 1024 * 1024,
                )
                # Exclusive output creation never replaces an existing archive.
                with ZipFile(
                    args.output, mode="x", compression=ZIP_DEFLATED
                ) as archive:
                    for name, content in journal_files(bundle).items():
                        archive.writestr(name, content)
                result = {
                    "archive": str(args.output),
                    "mission_id": args.mission,
                    "H": bundle.high_water,
                }
            elif args.command == "backup":
                result = {
                    "manifest": str(
                        backup_store(
                            store,
                            directory=args.directory
                            or settings.database_path.parent / "backups",
                        )
                    )
                }
            else:
                health = verify_store(store)
                result = health.model_dump(mode="json")
                if not health.ready:
                    print(json.dumps(result))
                    return 1
        print(json.dumps(result))
        return 0
    except OperatorError as error:
        print(
            json.dumps(
                {"ready": False, "error_code": error.code, "retryable": error.retryable}
            )
        )
        return 1
    except (ValueError, OSError) as error:
        print(
            json.dumps(
                {
                    "ready": False,
                    "error_code": (
                        "invalid_configuration"
                        if isinstance(error, ValueError)
                        else "store_unavailable"
                    ),
                }
            )
        )
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
