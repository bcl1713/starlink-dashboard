"""Thin private Compose launcher; reuses acceptance command/process ownership."""

import argparse
import importlib.util
import json
import os
import re
import signal
import sys
import tarfile
import time
from pathlib import Path
from uuid import uuid4

SOURCE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SOURCE / "tools/acceptance/operator-journal"))
from ownership import Owner, free_port, group_alive

spec = importlib.util.spec_from_file_location(
    "operator_training_scenario", Path(__file__).with_name("scenario.py")
)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)


def validate_project(project, root_id):
    expected = "starlink-operator-training-" + root_id.replace("-", "")[:12]
    if project != expected:
        raise ValueError(f"Use the private project {expected}")
    return expected


def validate_compose(config, root, project):
    expected = {"training-data", "training-routes"}
    volumes = config.get("volumes", {})
    if set(volumes) != expected or any(
        value.get("external") or value.get("name") != f"{project}_{name}"
        for name, value in volumes.items()
    ):
        raise ValueError("Only task-private Compose volumes are allowed")
    services = config.get("services", {})
    if set(services) != {"starlink-location", "mission-planner"}:
        raise ValueError("Only the private training application services are allowed")
    backend = services["starlink-location"]
    if backend.get("environment", {}).get("STARLINK_MODE") != "simulation":
        raise ValueError("Training requires simulation mode")
    allowed_binds = {
        str(root / "source"): "/source",
        str(root / scenario.MARKER): "/training-marker.json",
    }
    for service in services.values():
        if service.get("privileged") or service.get("network_mode") == "host":
            raise ValueError(
                "Private training cannot use host privileges or networking"
            )
        for mount in service.get("volumes", []):
            if mount["type"] == "volume":
                if mount["source"] not in expected or not mount.get("volume", {}).get(
                    "nocopy"
                ):
                    raise ValueError("Operational volume mounts are forbidden")
            elif (
                mount["type"] != "bind"
                or allowed_binds.get(mount["source"]) != mount["target"]
                or not mount.get("read_only")
            ):
                raise ValueError("Only readonly owned source/marker mounts are allowed")
        if any(port.get("host_ip") != "127.0.0.1" for port in service.get("ports", [])):
            raise ValueError("Training ports must bind loopback")
    if not config.get("networks", {}).get("default", {}).get("internal"):
        raise ValueError("Training requires a private internal network")


def open_owner(
    root, *, create=False, project=None, port=None, disposable=False, destination=False
):
    root = Path(root).absolute()
    marker = (
        scenario.mark_root(root)
        if create
        else json.loads((root / scenario.MARKER).read_text())
    )
    scenario.training_namespace(root, mode="simulation")
    expected = "starlink-operator-training-" + marker["root_id"].replace("-", "")[:12]
    validate_project(project or expected, marker["root_id"])
    state = root / "ownership.json"
    previous = json.loads(state.read_text()) if state.exists() else None
    if previous is not None and (
        not isinstance(previous, dict)
        or previous.get("project") != expected
        or previous.get("trainingRootId") != marker["root_id"]
    ):
        raise ValueError("Existing resource ownership does not match the marked root")
    if not previous and not create:
        raise ValueError("Recorded training ownership required")
    if previous and (
        previous.get("dockerHost") != os.environ.get("DOCKER_HOST")
        or previous.get("dockerContext") != os.environ.get("DOCKER_CONTEXT")
    ):
        raise ValueError(
            "Use the original configured Docker daemon/context for these owned resources"
        )
    if previous is not None:
        recorded_sha = previous.get("candidateSha")
        recorded_port = previous.get("port")
        if (
            not isinstance(recorded_sha, str)
            or not re.fullmatch("[0-9a-f]{40}", recorded_sha)
            or type(recorded_port) is not int
            or not 1024 <= recorded_port <= 65535
            or type(previous.get("disposable")) is not bool
            or not isinstance(previous.get("commands"), list)
        ):
            raise ValueError(
                "Invalid recorded training candidate, port or ownership schema; preserve for recovery"
            )
    if previous is not None and previous.get("destination") is not destination:
        raise ValueError(
            "Recorded training instance purpose does not match this command"
        )
    owner = Owner(expected, root)
    if previous:
        owner.ownership = previous | {"pid": os.getpid(), "pgid": os.getpgrp()}
    owner.compose_file = root / "source/docker-compose.operator-training.yml"
    if not previous:
        if not create:
            raise ValueError("Recorded training ownership required")
        sha = owner.execute(["git", "rev-parse", "HEAD"], cwd=SOURCE).strip()
        if not re.fullmatch("[0-9a-f]{40}", sha):
            raise ValueError("A committed source SHA is required")
        source = root / "source"
        if source.exists():
            raise ValueError(
                "Incomplete prior launch; preserve this root and reset into a new sibling"
            )
        owner.execute(
            [
                "git",
                "archive",
                "--format=tar",
                "--output",
                str(root / "source.tar"),
                sha,
            ],
            cwd=SOURCE,
        )
        source.mkdir()
        with tarfile.open(root / "source.tar") as archive:
            archive.extractall(source, filter="data")
        owner.ownership.update(
            candidateSha=sha,
            port=port or free_port(),
            trainingRootId=marker["root_id"],
            disposable=disposable,
            destination=destination,
            state="prepared",
        )
    sha = owner.ownership["candidateSha"]
    chosen_port = owner.ownership["port"]
    if (
        not re.fullmatch("[0-9a-f]{40}", sha)
        or not isinstance(chosen_port, int)
        or not 1024 <= chosen_port <= 65535
    ):
        raise ValueError("Invalid recorded training candidate or port")
    owner.ownership.update(
        composeFile=str(owner.compose_file),
        volumes=[f"{expected}_training-data", f"{expected}_training-routes"],
        fixture=marker["namespace"],
    )
    owner.env.update(
        OPERATOR_SOURCE_ROOT=str(root / "source"),
        ACCEPTANCE_CANDIDATE_SHA=sha,
        OPERATOR_TRAINING_PROJECT=expected,
        OPERATOR_TRAINING_ROOT_ID=marker["root_id"],
        OPERATOR_TRAINING_MARKER=str(root / scenario.MARKER),
        OPERATOR_TRAINING_PORT=str(chosen_port),
        OPERATOR_ACCEPTANCE_PORT=str(chosen_port),
        OPERATOR_TRAINING_ENTRYPOINT=(
            "archive_destination" if owner.ownership.get("destination") else "backend"
        ),
    )
    owner.persist()
    return owner


def check_resources(owner):
    """Never use a project label alone as authority to remove a resource."""
    selector = f"label=com.docker.compose.project={owner.project}"
    resources = {}
    for kind in ("container", "network", "volume"):
        command = ["docker", kind, "ls", "-q"]
        if kind == "container":
            command.append("-a")
        ids = owner.execute([*command, "--filter", selector]).split()
        resources[kind] = ids
        for identifier in ids:
            field = ".Config.Labels" if kind == "container" else ".Labels"
            labels = json.loads(
                owner.execute(
                    [
                        "docker",
                        kind,
                        "inspect",
                        "--format",
                        "{{json " + field + "}}",
                        identifier,
                    ]
                )
            )
            if (
                labels.get("operator.training.root")
                != owner.ownership["trainingRootId"]
            ):
                raise ValueError(
                    f"Unowned {kind} in private project; preserve and inspect it"
                )
    return resources


def stop_relay(owner):
    entry = owner.ownership.get("relay")
    if not entry:
        return
    pid = entry["pid"]
    path = Path(f"/proc/{pid}/cmdline")
    if path.exists():
        command = path.read_bytes().split(b"\0")
        expected = str(
            owner.root / "source/tools/acceptance/operator-journal/relay.py"
        ).encode()
        if expected not in command or os.getpgid(pid) != entry["pgid"]:
            raise ValueError("Relay ownership changed; refusing to signal this process")
        os.killpg(entry["pgid"], signal.SIGTERM)
        deadline = time.monotonic() + 10
        while group_alive(entry["pgid"]) and time.monotonic() < deadline:
            if owner.relay is not None:
                owner.relay.poll()
            time.sleep(0.05)
        if group_alive(entry["pgid"]):
            os.killpg(entry["pgid"], signal.SIGKILL)
        if owner.relay is not None:
            owner.relay.wait(timeout=10)
    owner.ownership.pop("relay", None)
    owner.persist()


def validate(owner):
    config = json.loads(owner.compose("config", "--format", "json"))
    validate_compose(config, owner.root, owner.project)
    return check_resources(owner)


def stop(owner, *, retain=False):
    validate(owner)
    child = owner.root / "import-destination"
    if (child / "ownership.json").exists():
        stop(open_owner(child, destination=True))
    stop_relay(owner)
    remove = owner.ownership.get("disposable", False) and not retain
    owner.compose("down", *(["--volumes"] if remove else []), timeout=120)
    remaining = check_resources(owner)
    if (
        remaining["container"]
        or remaining["network"]
        or (remove and remaining["volume"])
    ):
        raise RuntimeError(f"Training cleanup incomplete: {remaining}")
    owner.ownership.update(state="stopped", remaining=remaining)
    owner.persist()
    return remaining


def start(owner, *, relay=False):
    validate(owner)
    try:
        owner.compose("build", timeout=1200)
        owner.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=200)
        if relay:
            if owner.ownership.get("relay"):
                stop_relay(owner)
            container = owner.compose("ps", "-q", "mission-planner").strip()
            owner.start_relay(container)
        owner.ownership["state"] = "running"
        owner.persist()
    except BaseException:
        stop(owner)
        raise
    return f'http://127.0.0.1:{owner.ownership["port"]}/operator?workspace=1'


def reset_root(owner, *, disposable=False, relay=False):
    stop(owner, retain=True)
    successor = owner.root.with_name(owner.root.name + "-reset-" + uuid4().hex[:8])
    owner.ownership["resetSuccessor"] = str(successor)
    owner.persist()
    fresh = open_owner(successor, create=True, disposable=disposable)
    return {
        "retainedRoot": str(owner.root),
        "newRoot": str(successor),
        "origin": start(fresh, relay=relay),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "start",
            "stop",
            "reset",
            "checkpoint",
            "restart",
            "import-start",
            "import-stop",
            "archive-inputs",
            "journal-check",
            "journal-backup",
            "journal-restore",
        ],
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--project")
    parser.add_argument("--port", type=int)
    parser.add_argument(
        "--disposable",
        action="store_true",
        help="Remove private data volumes when stopped; only for automated checks",
    )
    parser.add_argument(
        "--relay",
        action="store_true",
        help="Use the existing owned relay for an isolated managed Docker namespace",
    )
    parser.add_argument("--stage", choices=list(scenario.CHECKPOINTS))
    parser.add_argument("--manifest")
    parser.add_argument("--browser-origin")
    args = parser.parse_args()
    root = args.root.absolute()
    destination = args.command.startswith("import-")
    if destination:
        scenario.training_namespace(root, mode="simulation")
        root = root / "import-destination"
    creating = args.command in ("start", "import-start")
    owner = open_owner(
        root,
        create=creating,
        project=args.project,
        port=args.port,
        disposable=args.disposable or destination,
        destination=destination,
    )
    handlers = {
        number: signal.signal(number, owner.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        if args.command in ("start", "import-start"):
            print(
                json.dumps(
                    {
                        "origin": start(owner, relay=args.relay),
                        "owner": str(root / "ownership.json"),
                        "stop": f'scripts/operator-training.sh {"import-stop" if destination else "stop"} --root {args.root}',
                    }
                )
            )
        elif args.command in ("stop", "import-stop"):
            print(json.dumps({"cleanup": stop(owner)}))
        elif args.command == "restart":
            validate(owner)
            owner.compose("restart", "starlink-location", timeout=120)
            print(json.dumps({"restarted": owner.project}))
        elif args.command.startswith("journal-"):
            spec = importlib.util.spec_from_file_location(
                "operator_training_recovery_control",
                Path(__file__).with_name("recovery_control.py"),
            )
            recovery = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(recovery)
            print(
                json.dumps(
                    recovery.run(
                        owner,
                        args.command.removeprefix("journal-"),
                        manifest=args.manifest,
                        origin=args.browser_origin,
                    )
                )
            )
        elif args.command == "archive-inputs":
            validate(owner)
            print(
                owner.compose(
                    "exec",
                    "-T",
                    "--user",
                    "appuser",
                    "starlink-location",
                    "python",
                    "/source/tools/training/operator-mission/archive_inputs.py",
                    "/app/data",
                    timeout=180,
                )
            )
        elif args.command == "checkpoint":
            if not args.stage:
                raise ValueError("--stage is required")
            validate(owner)
            print(
                owner.compose(
                    "exec",
                    "-T",
                    "--user",
                    "appuser",
                    "starlink-location",
                    "python",
                    "/source/tools/training/operator-mission/control.py",
                    "/app/data",
                    args.stage,
                )
            )
        elif args.command == "reset":
            print(
                json.dumps(
                    reset_root(owner, disposable=args.disposable, relay=args.relay)
                )
            )
    finally:
        owner.stop_child()
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    main()
