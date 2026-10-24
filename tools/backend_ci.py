"""Observe pytest without selecting tests or changing their execution semantics.

Schema 1 keeps ordered inventories and individual phase events, including failures
and missing phases, so later consumers can validate completeness without guessing.
Only explicitly supplied run metadata is read from the environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(config):
    root = Path(__file__).resolve().parent.parent
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    inventory = sorted(d.metadata["Name"] + "==" + d.version for d in distributions())
    backend = root / "backend/starlink-location"
    inputs = [*backend.glob("requirements*.txt"), backend / "pytest.ini"]
    return {
        "checkout_sha": revision,
        "github_sha": os.environ.get("GITHUB_SHA"),
        "pr_head_sha": os.environ.get("BACKEND_CI_PR_HEAD_SHA"),
        "run_id": os.environ.get("BACKEND_CI_RUN_ID", os.environ.get("GITHUB_RUN_ID")),
        "run_attempt": os.environ.get(
            "BACKEND_CI_RUN_ATTEMPT", os.environ.get("GITHUB_RUN_ATTEMPT")
        ),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "shard": {"index": None, "count": None},
        "observer_sha256": _sha256(Path(__file__)),
        "input_sha256": {
            str(path.relative_to(root)): _sha256(path) for path in sorted(inputs)
        },
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "distributions": inventory,
        "distribution_sha256": hashlib.sha256(
            "\n".join(inventory).encode()
        ).hexdigest(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
            "image_os": os.environ.get("ImageOS"),
            "image_version": os.environ.get("ImageVersion"),
        },
        "command": list(sys.orig_argv),
        "pytest_args": list(config.invocation_params.args),
        "cwd": str(Path.cwd()),
        "cache_state": os.environ.get("BACKEND_CI_CACHE_STATE", "unknown"),
    }


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            name = stream.name
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def pytest_addoption(parser):
    group = parser.getgroup("backend-ci")
    group.addoption(
        "--backend-ci-report",
        metavar="ABS_JSON",
        help="Write an atomic observation report",
    )


def pytest_configure(config):
    path = config.getoption("backend_ci_report")
    if path is None:
        return
    if not Path(path).is_absolute():
        import pytest

        raise pytest.UsageError("--backend-ci-report requires an absolute path")
    config.pluginmanager.register(_Observer(config, Path(path)), "backend-ci-observer")


class _Observer:
    def __init__(self, config, path):
        self.path = path
        self.started = time.monotonic()
        self.collection_started = None
        self.report = {
            "schema_version": 1,
            "identity": _identity(config),
            "session": {
                "started_at": _now(),
                "ended_at": None,
                "duration_seconds": None,
                "exit_code": None,
                "finished": False,
                "collect_only": bool(config.option.collectonly),
                "interrupted": None,
                "internal_errors": [],
            },
            "collection": {
                "full_nodeids": [],
                "selected_nodeids": [],
                "deselected_nodeids": [],
                "errors": [],
                "duration_seconds": None,
            },
            "phases": [],
        }

    def pytest_sessionstart(self, session):
        self.collection_started = time.monotonic()

    def pytest_collectreport(self, report):
        if report.failed:
            self.report["collection"]["errors"].append(
                {"nodeid": report.nodeid, "longrepr": str(report.longrepr)}
            )

    def pytest_collection_finish(self, session):
        collection = self.report["collection"]
        nodeids = [item.nodeid for item in session.items]
        collection["full_nodeids"] = nodeids
        collection["selected_nodeids"] = list(nodeids)
        collection["duration_seconds"] = time.monotonic() - self.collection_started

    def pytest_runtest_logreport(self, report):
        self.report["phases"].append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "duration": report.duration,
                "wasxfail": getattr(report, "wasxfail", None),
                "longrepr": (
                    str(report.longrepr) if report.longrepr is not None else None
                ),
                "start": report.start,
                "stop": report.stop,
            }
        )

    def pytest_keyboard_interrupt(self, excinfo):
        self.report["session"]["interrupted"] = repr(excinfo.value)

    def pytest_internalerror(self, excrepr, excinfo):
        self.report["session"]["internal_errors"].append(str(excrepr))

    def pytest_sessionfinish(self, session, exitstatus):
        self.report["session"].update(
            ended_at=_now(),
            duration_seconds=time.monotonic() - self.started,
            exit_code=int(exitstatus),
            finished=True,
        )
        _atomic_json(self.path, self.report)
