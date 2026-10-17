"""Explicit local maintenance: python -m app.operator COMMAND --root --mode."""

import argparse
import json
from pathlib import Path

from .backup import backup_store
from .clock import SystemClock
from .errors import OperatorError
from .recovery import restore_store, verify_store
from .settings import OperatorSettings
from .store import OperatorStore


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline Operator administration; restore replaces the whole store."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("initialize", "check", "backup", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--mode", choices=("live", "simulation"), required=True)
        command.add_argument("--run", help="Required simulation run ID")
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
        )
        clock = SystemClock()
        if args.command == "restore":
            health = restore_store(settings, manifest=args.manifest, clock=clock)
            result = health.model_dump(mode="json")
        else:
            store = OperatorStore.open(
                settings, initialize=args.command == "initialize", clock=clock
            )
            if args.command == "backup":
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
