"""Observe pytest inventories/phases and validate exhaustive backend shard evidence.

Serial observations use schema 1; shard schema 3 requires collector-skip evidence
and binds the report to its canonical resource owner's run and command context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARD_CONFIG = ROOT / "tools/backend_shards.json"

BACKEND_LOCK_INPUTS = (
    "requirements-dev.txt",
    "requirements.txt",
    "requirements-gfs.txt",
    ".python-version",
)
BACKEND_LOCK_HEADER = "# backend-lock-input-sha256: "


def backend_commands(root, python_selector):
    """The single canonical serial inventory/pytest pipeline, shared with its gate."""
    backend = Path(root) / "backend/starlink-location"
    uv = [
        "uv",
        "run",
        "--python",
        python_selector,
        "--isolated",
        "--with-requirements",
        str(backend / "requirements-dev.txt"),
        "--with-requirements",
        str(backend / "requirements-gfs.txt"),
        "--with-requirements",
        str(backend / "requirements-ci.txt"),
    ]
    return [
        (
            [
                *uv,
                "python",
                "-c",
                (
                    "import sys; from importlib.metadata import distributions; "
                    "print('Python:', sys.version, 'executable:', sys.executable, flush=True); "
                    "assert sys.version_info[:2] == (3, 11), 'backend requires Python 3.11'; "
                    "print('Installed distributions:\\n' + '\\n'.join(sorted("
                    "d.metadata['Name'] + '==' + d.version for d in distributions())))"
                ),
            ],
            backend,
        ),
        (
            [*uv, "pytest", "tests/", "-q", "--durations=50", "--durations-min=0"],
            backend,
        ),
    ]


def backend_lock_input_hashes(root):
    """Fingerprint all canonical dependency sources and the tracked interpreter."""
    backend = root / "backend/starlink-location"
    return {name: _sha256(backend / name) for name in BACKEND_LOCK_INPUTS}


def validate_backend_lock(root):
    """Reject stale or missing lock provenance before resolving dependencies."""
    try:
        lock = root / "backend/starlink-location/requirements-ci.txt"
        headers = [
            line.removeprefix(BACKEND_LOCK_HEADER)
            for line in lock.read_text().splitlines()
            if line.startswith(BACKEND_LOCK_HEADER)
        ]
        if len(headers) != 1 or json.loads(headers[0]) != backend_lock_input_hashes(
            root
        ):
            raise ValueError("source fingerprints differ")
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(
            "Backend dependency lock is missing or stale; regenerate requirements-ci.txt "
            "with uv pip compile --generate-hashes using requirements-dev.txt and "
            "requirements-gfs.txt plus reviewed inventory constraints, then update the "
            "backend-lock-input-sha256 header with backend_lock_input_hashes(ROOT)."
        ) from error


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
    inputs = [
        *backend.glob("requirements*.txt"),
        backend / "pytest.ini",
        backend / ".python-version",
    ]
    return {
        "checkout_sha": revision,
        "github_sha": os.environ.get("GITHUB_SHA"),
        "pr_head_sha": os.environ.get("BACKEND_CI_PR_HEAD_SHA"),
        "run_id": os.environ.get("BACKEND_CI_RUN_ID", os.environ.get("GITHUB_RUN_ID")),
        "run_attempt": os.environ.get(
            "BACKEND_CI_RUN_ATTEMPT", os.environ.get("GITHUB_RUN_ATTEMPT")
        ),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "shard": parse_shard(config.getoption("backend_ci_shard")),
        "checkout_path": str(root),
        "report_path": config.getoption("backend_ci_report"),
        "owner_context": (
            _decode_json(os.environ["BACKEND_CI_OWNER_CONTEXT"])
            if os.environ.get("BACKEND_CI_OWNER_CONTEXT")
            else None
        ),
        "runner_sha256": (
            _sha256(root / "tools/backend_test_runner.py")
            if (root / "tools/backend_test_runner.py").exists()
            else None
        ),
        "verify_sha256": _sha256(root / "tools/verify"),
        "config_sha256": _sha256(Path(config.getoption("backend_ci_config"))),
        "backend_tree": subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD:backend/starlink-location"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip(),
        "uv_version": subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, check=True, timeout=10
        ).stdout.strip(),
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

    group.addoption("--backend-ci-shard", metavar="N/4", default=None)
    group.addoption("--backend-ci-config", default=str(SHARD_CONFIG))


def pytest_configure(config):
    path = config.getoption("backend_ci_report")
    if path is None:
        return
    if not Path(path).is_absolute():
        import pytest

        raise pytest.UsageError("--backend-ci-report requires an absolute path")
    import pytest

    try:
        reject_pytest_overrides(os.environ)
        shard = parse_shard(config.getoption("backend_ci_shard"))
        if shard["index"] is not None and (
            config.option.keyword
            or config.option.markexpr
            or config.option.maxfail
            or list(config.args) != ["tests/"]
        ):
            raise ValueError("shards require unfiltered full tests/ collection")
        observer = _Observer(config, Path(path))
        if observer.report["identity"]["owner_context"] is not None:
            validate_owner_context(observer.report["identity"])
    except (ValueError, OSError) as error:
        raise pytest.UsageError(str(error)) from error
    pytest.hookimpl(tryfirst=True)(_Observer.pytest_collection_modifyitems)
    config.pluginmanager.register(observer, "backend-ci-observer")


class _Observer:
    def __init__(self, config, path):
        self.path = path
        self.started = time.monotonic()
        self.collection_started = None
        self.config = config
        self.shards = load_shard_config(Path(config.getoption("backend_ci_config")))
        self.shard = parse_shard(config.getoption("backend_ci_shard"))
        self.report = {
            "schema_version": 3 if self.shard["index"] is not None else 1,
            "allowed_existing_nonpasses": self.shards["allowed_existing_nonpasses"],
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
                "skipped_collectors": [],
                "duration_seconds": None,
            },
            "phases": [],
        }

    def pytest_sessionstart(self, session):
        self.collection_started = time.monotonic()

    def pytest_collectreport(self, report):
        if report.skipped:
            self.report["collection"]["skipped_collectors"].append(
                {
                    "nodeid": report.nodeid,
                    "reason": (
                        str(report.longrepr[2])
                        if isinstance(report.longrepr, tuple)
                        else str(report.longrepr)
                    ),
                }
            )
        if report.failed:
            self.report["collection"]["errors"].append(
                {"nodeid": report.nodeid, "longrepr": str(report.longrepr)}
            )

    def pytest_collection_modifyitems(self, session, config, items):
        collection = self.report["collection"]
        full = [item.nodeid for item in items]
        if len(set(full)) != len(full):
            raise ValueError("duplicate collected node IDs")
        paths = {
            item.nodeid: item.path.resolve()
            .relative_to(config.rootpath.resolve())
            .as_posix()
            for item in items
        }
        mapping = (
            {
                path: assign_file(path, 4, self.shards["overrides"])
                for path in sorted(set(paths.values()))
            }
            if self.shard["index"] is not None
            else {}
        )
        selected, deselected = [], []
        for item in items:
            target = (
                selected
                if (
                    self.shard["index"] is None
                    or mapping[paths[item.nodeid]] == self.shard["index"]
                )
                else deselected
            )
            target.append(item)
        collection.update(
            full_nodeids=full,
            selected_nodeids=[item.nodeid for item in selected],
            deselected_nodeids=[item.nodeid for item in deselected],
            nodeid_paths=paths,
            file_assignments=mapping,
            assignment_sha256=assignment_digest(mapping),
            stale_overrides=sorted(set(self.shards["overrides"]) - set(paths.values())),
        )
        if self.shard["index"] is not None and not selected:
            raise ValueError("empty selected shard")
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected

    def pytest_collection_finish(self, session):
        collection = self.report["collection"]
        if [item.nodeid for item in session.items] != collection["selected_nodeids"]:
            raise ValueError("another plugin altered the collected shard inventory")
        collection["duration_seconds"] = time.monotonic() - self.collection_started

    def pytest_runtest_logreport(self, report):
        self.report["phases"].append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "duration": report.duration,
                "wasxfail": getattr(report, "wasxfail", None),
                "skip_reason": (
                    str(report.longrepr[2]).replace(str(ROOT), "${CHECKOUT}")
                    if report.skipped and isinstance(report.longrepr, tuple)
                    else None
                ),
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
        write_summary(self.path.with_suffix(".md"), self.report)


def read_json(path):
    """Decode evidence without JSON's permissive duplicate/nonfinite extensions."""
    return _decode_json(Path(path).read_text())


def _decode_json(source):

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON number: {value}")

    result = json.loads(source, object_pairs_hook=pairs, parse_constant=constant)

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        if isinstance(value, list):
            for child in value:
                finite(child)

    finite(result)
    return result


def parse_shard(value):
    if value is None:
        return {"index": None, "count": None}
    if not isinstance(value, str) or re.fullmatch(r"[1-4]/4", value) is None:
        raise ValueError("shard must be N/4 with N between 1 and 4")
    return {"index": int(value[0]), "count": 4}


def reject_pytest_overrides(environment):
    for name in (
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_DEBUG",
    ):
        if environment.get(name):
            raise ValueError(f"unexpected inherited pytest override: {name}")


def assign_file(path, shard_count, overrides):
    """Choose one whole collected file, with stable default placement for new files."""
    if type(shard_count) is not int or shard_count != 4:
        raise ValueError("exactly four shards are required")
    if (
        not isinstance(path, str)
        or not path.startswith("tests/")
        or "\\" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise ValueError(f"invalid collection path: {path!r}")
    if path in overrides:
        index = overrides[path]
        if type(index) is not int or index not in range(1, 5):
            raise ValueError(f"invalid shard assignment for {path}: {index!r}")
        return index
    return int.from_bytes(hashlib.sha256(path.encode()).digest(), "big") % 4 + 1


def load_shard_config(path=SHARD_CONFIG):
    value = read_json(path)
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or type(value.get("shard_count")) is not int
        or value["shard_count"] != 4
        or not isinstance(value.get("overrides"), dict)
    ):
        raise ValueError("unsupported or malformed shard configuration")
    for name in value["overrides"]:
        assign_file(name, 4, value["overrides"])
    allowed = value.get("allowed_existing_nonpasses")
    if not isinstance(allowed, list) or any(
        not isinstance(entry, dict) for entry in allowed
    ):
        raise ValueError("missing baseline nonpass semantics")
    seen = set()
    for entry in allowed:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"nodeid", "outcome", "reason"}
            or not all(isinstance(v, str) and v for v in entry.values())
            or entry["outcome"] != "skipped"
            or entry["nodeid"] in seen
        ):
            raise ValueError("invalid baseline nonpass semantics")
        seen.add(entry["nodeid"])
    return value


def assignment_digest(mapping):
    return hashlib.sha256(
        json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def backend_pipeline(commands, report, run_root, shard):
    """Record the exact reported command plan before any owned process starts."""
    pipeline = []
    for index, (command, cwd) in enumerate(commands):
        command = list(command)
        if "pytest" in command:
            command += [
                "-p",
                "backend_ci",
                f"--backend-ci-report={report}",
                f"--basetemp={Path(run_root) / 'basetemp'}",
            ]
            if shard:
                command += [f"--backend-ci-shard={shard}"]
        pipeline.append(
            {
                "label": "inventory" if index == 0 else "pytest",
                "command": command,
                "cwd": str(cwd),
            }
        )
    return pipeline


def _absolute_record_path(value, label):
    if (
        not isinstance(value, str)
        or not Path(value).is_absolute()
        or any(part in (".", "..") for part in value.split("/"))
    ):
        raise ValueError(f"{label} must record an absolute path without traversal")
    return Path(value)


def expected_owner_context(identity, run_root, python_selector):
    """Reconstruct canonical argv in the artifact's own recorded path context."""
    checkout = _absolute_record_path(identity["checkout_path"], "checkout")
    report = _absolute_record_path(identity["report_path"], "report")
    private = _absolute_record_path(run_root, "run root")
    if private == report.parent or private in report.parents:
        raise ValueError("recorded report must be outside its private root")
    if not isinstance(python_selector, str) or not python_selector:
        raise ValueError("missing canonical Python selector")
    shard = identity["shard"]
    if shard == {"index": None, "count": None}:
        selection = None
    else:
        if (
            not isinstance(shard, dict)
            or set(shard) != {"index", "count"}
            or type(shard["index"]) is not int
            or shard["index"] not in range(1, 5)
            or type(shard["count"]) is not int
            or shard["count"] != 4
        ):
            raise ValueError("invalid owner shard selection")
        selection = f"{shard['index']}/4"
    pipeline = backend_pipeline(
        backend_commands(checkout, python_selector), report, private, selection
    )
    return {
        "schema_version": 1,
        "run_id": identity["run_id"],
        "run_attempt": identity["run_attempt"],
        "checkout_sha": identity["checkout_sha"],
        "checkout": str(checkout),
        "cwd": str(checkout / "backend/starlink-location"),
        "report": str(report),
        "run_root": str(private),
        "shard": shard,
        "python_selector": python_selector,
        "verify_sha256": identity["verify_sha256"],
        "pipeline": pipeline,
        "pipeline_sha256": assignment_digest(pipeline),
    }


def make_owner_context(repo, commands, report, run_root, shard):
    """Bind the producer's source/run identity to its canonical planned commands."""
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    try:
        command = commands[0][0]
        selector = command[command.index("--python") + 1]
    except (IndexError, ValueError) as error:
        raise ValueError(
            "reported pytest pipeline lacks its canonical inventory command"
        ) from error
    identity = {
        "checkout_path": str(repo),
        "report_path": str(report),
        "checkout_sha": revision,
        "shard": parse_shard(shard),
        "run_id": os.environ.get("BACKEND_CI_RUN_ID", os.environ.get("GITHUB_RUN_ID")),
        "run_attempt": os.environ.get(
            "BACKEND_CI_RUN_ATTEMPT", os.environ.get("GITHUB_RUN_ATTEMPT")
        ),
        "verify_sha256": _sha256(Path(repo) / "tools/verify"),
    }
    context = expected_owner_context(identity, str(run_root), selector)
    if backend_pipeline(commands, report, run_root, shard) != context["pipeline"]:
        raise ValueError(
            "reported pytest pipeline differs from canonical inventory/pytest argv"
        )
    return context


def validate_owner_context(identity):
    context = identity["owner_context"]
    if not isinstance(context, dict) or not context:
        raise ValueError("missing owner context")
    expected = expected_owner_context(
        identity, context["run_root"], context["python_selector"]
    )
    # JSON equality distinguishes bool/int as well as missing/extra context keys.
    if assignment_digest(context) != assignment_digest(expected):
        raise ValueError(
            "owner context differs from observed run/source/selection identity"
        )
    if identity["cwd"] != expected["cwd"]:
        raise ValueError("observation cwd differs from its checkout backend context")
    pytest_command = expected["pipeline"][1]["command"]
    if identity["pytest_args"] != pytest_command[pytest_command.index("pytest") + 1 :]:
        raise ValueError(
            "observed pytest args differ from the canonical owner selection"
        )
    return expected


def validate_ownership(report, ownership):
    """Require the exact owner and successful inventory→pytest pipeline for a report."""
    context = validate_owner_context(report["identity"])
    if (
        not isinstance(ownership, dict)
        or assignment_digest(ownership.get("context")) != assignment_digest(context)
        or ownership.get("checkout") != context["checkout"]
        or ownership.get("report") != context["report"]
        or ownership.get("shard") != f"{context['shard']['index']}/4"
    ):
        raise ValueError("ownership belongs to a different run/checkout/shard/report")
    commands = ownership.get("commands")
    if not isinstance(commands, list) or len(commands) != 2:
        raise ValueError("ownership requires successful inventory then pytest records")
    for actual, planned in zip(commands, context["pipeline"], strict=True):
        if (
            not isinstance(actual, dict)
            or {key: actual.get(key) for key in ("label", "command", "cwd")} != planned
            or type(actual.get("exit_code")) is not int
            or actual["exit_code"] != 0
            or type(actual.get("subprocess_returncode")) is not int
            or actual["subprocess_returncode"] != 0
            or actual.get("harness_error")
            or actual.get("cleanup_error")
        ):
            raise ValueError(
                "ownership command/order/cwd/status differs from the planned pipeline"
            )
    if (
        ownership.get("cleanup") != {"survivors": [], "listeners": []}
        or ownership.get("private_paths_removed") is not True
    ):
        raise ValueError("runner cleanup evidence failed")


def check_needs(needs):
    expected = {f"backend_{i}" for i in range(1, 5)}
    if not isinstance(needs, dict) or set(needs) != expected:
        actual = set(needs) if isinstance(needs, dict) else set()
        raise ValueError(
            f"expected exactly backend_1..backend_4 jobs; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}"
        )
    for name in sorted(expected):
        if not isinstance(needs[name], dict) or needs[name].get("result") != "success":
            raise ValueError(f"{name} did not succeed: {needs[name]!r}")


def _strings(value, label):
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty strings")
    return value


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {label}: {value!r}")


def _unique(value, label):
    result = _strings(value, label)
    if len(set(result)) != len(result):
        raise ValueError(f"duplicate {label}")
    return result


SEMANTIC_IDENTITIES = (
    "checkout_sha",
    "github_sha",
    "pr_head_sha",
    "run_id",
    "run_attempt",
    "workflow",
    "observer_sha256",
    "runner_sha256",
    "verify_sha256",
    "config_sha256",
    "input_sha256",
    "backend_tree",
    "uv_version",
    "distributions",
    "distribution_sha256",
)


def validate_reports(reports, expected_identity, needs_results):
    """Fail closed on status, identity, coverage and per-case phase evidence."""
    try:
        return _validate_reports(reports, expected_identity, needs_results)
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise ValueError(f"malformed backend evidence: {error}") from error


def _validate_reports(reports, expected_identity, needs_results):
    check_needs(needs_results)
    if not isinstance(reports, list) or len(reports) != 4:
        raise ValueError("exactly four reports are required")
    all_selected = []
    reference = None
    outcomes = Counter()
    timings = []
    indices = set()
    for report in reports:
        if type(report["schema_version"]) is not int or report["schema_version"] != 3:
            raise ValueError("unsupported report schema")
        identity = report["identity"]
        shard = identity["shard"]
        index = shard["index"]
        if (
            type(index) is not int
            or index not in range(1, 5)
            or index in indices
            or type(shard["count"]) is not int
            or shard["count"] != 4
        ):
            raise ValueError("invalid or duplicate shard identity")
        indices.add(index)
        for key, value in expected_identity.items():
            if identity.get(key) != value or type(identity.get(key)) is not type(value):
                raise ValueError(f"unexpected {key} in shard {index}")
        if identity["checkout_sha"] != identity["github_sha"]:
            raise ValueError("actual checkout does not match github.sha")
        for key in ("checkout_sha", "github_sha", "backend_tree"):
            if (
                not isinstance(identity[key], str)
                or re.fullmatch(r"[0-9a-f]{40}", identity[key]) is None
            ):
                raise ValueError(f"invalid {key}")
        for key in (
            "observer_sha256",
            "runner_sha256",
            "verify_sha256",
            "config_sha256",
            "distribution_sha256",
        ):
            if (
                not isinstance(identity[key], str)
                or re.fullmatch(r"[0-9a-f]{64}", identity[key]) is None
            ):
                raise ValueError(f"invalid {key}")
        inventory = _strings(identity["distributions"], "distribution multiset")
        if (
            not inventory
            or inventory != sorted(inventory)
            or hashlib.sha256("\n".join(inventory).encode()).hexdigest()
            != identity["distribution_sha256"]
        ):
            raise ValueError("distribution multiset or digest mismatch")
        if (
            not isinstance(identity["input_sha256"], dict)
            or not identity["input_sha256"]
        ):
            raise ValueError("missing source input hashes")
        for name, digest in identity["input_sha256"].items():
            if (
                not isinstance(name, str)
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise ValueError("invalid source input hash")
        python = identity["python"]
        if not all(
            isinstance(python[key], str) and python[key]
            for key in ("version", "implementation", "executable")
        ):
            raise ValueError("invalid interpreter identity")
        semantic = {key: identity[key] for key in SEMANTIC_IDENTITIES}
        semantic["python"] = {key: python[key] for key in ("version", "implementation")}
        allowed = report["allowed_existing_nonpasses"]
        if not isinstance(allowed, list) or any(
            not isinstance(entry, dict) for entry in allowed
        ):
            raise ValueError("missing allowed existing nonpasses")
        semantic["allowed_existing_nonpasses"] = allowed
        collection = report["collection"]
        if collection["skipped_collectors"] != []:
            raise ValueError(
                "unexpected skipped collector: no collection skips are approved"
            )
        full = _unique(collection["full_nodeids"], "full node IDs")
        selected = _unique(collection["selected_nodeids"], "selected node IDs")
        deselected = _unique(collection["deselected_nodeids"], "deselected node IDs")
        if not full or not selected:
            raise ValueError("empty collection or shard")
        mapping = collection["file_assignments"]
        paths = collection["nodeid_paths"]
        if (
            not isinstance(mapping, dict)
            or not isinstance(paths, dict)
            or set(paths) != set(full)
        ):
            raise ValueError("incomplete collected file ownership")
        if set(mapping) != set(paths.values()):
            raise ValueError("incomplete file assignments")
        for path in mapping:
            assign_file(path, 4, mapping)
        if assignment_digest(mapping) != collection["assignment_sha256"]:
            raise ValueError("assignment digest mismatch")
        wanted = [node for node in full if mapping[paths[node]] == index]
        if selected != wanted or deselected != [
            node for node in full if mapping[paths[node]] != index
        ]:
            raise ValueError("selected/deselected inventory does not match assignments")
        semantic.update(full_nodeids=full, file_assignments=mapping, nodeid_paths=paths)
        if reference is None:
            reference = semantic
        elif semantic != reference:
            raise ValueError(f"shard {index} source/environment/full inventory differs")
        session = report["session"]
        if (
            session["finished"] is not True
            or type(session["exit_code"]) is not int
            or session["exit_code"] != 0
            or session["collect_only"] is not False
            or session["interrupted"] is not None
            or session["internal_errors"] != []
            or collection["errors"] != []
        ):
            raise ValueError(f"shard {index} session or collection failed/incomplete")
        _number(session["duration_seconds"], "session duration")
        _number(collection["duration_seconds"], "collection duration")
        events = {node: {} for node in selected}
        if not isinstance(report["phases"], list) or any(
            not isinstance(phase, dict) for phase in report["phases"]
        ):
            raise ValueError("phases must be an array")
        for phase in report["phases"]:
            node, when = phase["nodeid"], phase["when"]
            if (
                node not in events
                or when not in ("setup", "call", "teardown")
                or when in events[node]
            ):
                raise ValueError("extra, duplicate or unknown phase")
            if phase["outcome"] not in ("passed", "skipped", "failed"):
                raise ValueError("invalid phase outcome")
            _number(phase["duration"], "phase duration")
            if phase["outcome"] == "failed" or phase["wasxfail"] is not None:
                raise ValueError("failed phase or unexpected xfail/xpass")
            events[node][when] = phase
        allowed_map = {entry["nodeid"]: entry for entry in allowed}
        if len(allowed_map) != len(allowed):
            raise ValueError("duplicate nonpass allowance")
        for node, phases in events.items():
            if (
                "setup" not in phases
                or "teardown" not in phases
                or phases["teardown"]["outcome"] != "passed"
            ):
                raise ValueError(
                    f"missing setup/teardown or unsuccessful teardown: {node}"
                )
            setup = phases["setup"]
            terminal = setup if setup["outcome"] == "skipped" else phases.get("call")
            expected_phases = (
                {"setup", "teardown"}
                if setup["outcome"] == "skipped"
                else {"setup", "call", "teardown"}
            )
            expected_order = (
                ["setup", "teardown"]
                if setup["outcome"] == "skipped"
                else ["setup", "call", "teardown"]
            )
            if (
                terminal is None
                or set(phases) != expected_phases
                or list(phases) != expected_order
            ):
                raise ValueError(f"missing/extra terminal phase: {node}")
            outcome = terminal["outcome"]
            if outcome == "skipped":
                actual = {
                    "nodeid": node,
                    "outcome": "skipped",
                    "reason": terminal["skip_reason"],
                }
                if allowed_map.get(node) != actual:
                    raise ValueError(f"unexpected skip identity/reason: {node}")
            elif outcome != "passed":
                raise ValueError(f"unsuccessful terminal outcome: {node}")
            outcomes[outcome] += 1
        all_selected += selected
        timings.append(
            {
                "shard": index,
                "cases": len(selected),
                "collection_seconds": collection["duration_seconds"],
                "pytest_seconds": session["duration_seconds"],
                "phase_seconds": sum(p["duration"] for p in report["phases"]),
            }
        )
    if len(set(all_selected)) != len(all_selected) or Counter(all_selected) != Counter(
        reference["full_nodeids"]
    ):
        raise ValueError("shard union is incomplete or overlaps")
    return {
        "cases": len(all_selected),
        "outcomes": dict(outcomes),
        "shards": sorted(timings, key=lambda t: t["shard"]),
    }


def write_summary(path, report):
    phases = report["phases"]
    counts = Counter(
        event["outcome"]
        for event in phases
        if event["when"] == "call"
        or (event["when"] == "setup" and event["outcome"] != "passed")
    )
    files = Counter()
    paths = report["collection"].get("nodeid_paths", {})
    for event in phases:
        files[paths.get(event["nodeid"], event["nodeid"])] += event["duration"]
    lines = [
        "# Backend observation",
        "",
        f"Selected cases: {len(report['collection']['selected_nodeids'])}",
        f"Outcomes: {dict(counts)}",
        f"Collection seconds: {report['collection']['duration_seconds']}",
        f"Pytest seconds: {report['session']['duration_seconds']}",
        "",
        "Slow files (sum of setup/call/teardown):",
        "",
    ]
    lines.extend(
        f"- `{name}`: {seconds:.3f}s" for name, seconds in files.most_common(20)
    )
    lines.extend(["", "Skipped/xfail phases:", ""])
    lines.extend(
        f"- `{event['nodeid']}`: {event.get('skip_reason') or event.get('wasxfail')}"
        for event in phases
        if event["outcome"] == "skipped" or event.get("wasxfail")
    )
    Path(path).write_text("\n".join(lines) + "\n")


def report_name(run_id, attempt, index):
    return f"backend-report-{run_id}-{attempt}-{index}"


def _source_identity():
    backend = ROOT / "backend/starlink-location"
    return {
        "observer_sha256": _sha256(Path(__file__)),
        "runner_sha256": _sha256(ROOT / "tools/backend_test_runner.py"),
        "verify_sha256": _sha256(ROOT / "tools/verify"),
        "config_sha256": _sha256(SHARD_CONFIG),
        "input_sha256": {
            str(p.relative_to(ROOT)): _sha256(p)
            for p in sorted(
                [
                    *backend.glob("requirements*.txt"),
                    backend / "pytest.ini",
                    backend / ".python-version",
                ]
            )
        },
        "backend_tree": subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD:backend/starlink-location"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip(),
    }


def gate_artifacts(directory, expected, needs):
    directory = Path(directory)
    names = {
        report_name(expected["run_id"], expected["run_attempt"], i) for i in range(1, 5)
    }
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != names:
        raise ValueError("missing, extra or stale backend artifact directories")
    reports = []
    config = load_shard_config()
    for i in range(1, 5):
        name = report_name(expected["run_id"], expected["run_attempt"], i)
        artifact = directory / name
        candidates = list(artifact.rglob("backend-report-*.json"))
        if (
            not artifact.is_dir()
            or len(candidates) != 1
            or candidates[0] != artifact / f"{name}.json"
        ):
            raise ValueError(f"missing, extra or wrongly named report: {name}")
        report = read_json(candidates[0])
        if report["identity"]["shard"]["index"] != i:
            raise ValueError("report filename/shard identity mismatch")
        if report["allowed_existing_nonpasses"] != config["allowed_existing_nonpasses"]:
            raise ValueError("altered skip allowances")
        mapping = report["collection"]["file_assignments"]
        if mapping != {
            path: assign_file(path, 4, config["overrides"]) for path in mapping
        }:
            raise ValueError("altered reviewed file assignment")
        if Path(report["identity"]["report_path"]).name != f"{name}.json":
            raise ValueError("recorded report path does not match artifact identity")
        validate_ownership(report, read_json(artifact / "ownership.json"))
        reports.append(report)
    return validate_reports(reports, expected, needs)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate exhaustive backend shard evidence"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("check-needs")
    preflight.add_argument("--needs-json", type=Path, required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--needs-json", type=Path, required=True)
    gate.add_argument("--reports", type=Path, required=True)
    gate.add_argument("--sha", required=True)
    gate.add_argument("--run-id", required=True)
    gate.add_argument("--attempt", required=True)
    gate.add_argument("--pr-head-sha", required=True)
    args = parser.parse_args(argv)
    try:
        needs = read_json(args.needs_json)
        check_needs(needs)
        if args.command == "gate":
            expected = {
                "checkout_sha": args.sha,
                "github_sha": args.sha,
                "run_id": args.run_id,
                "run_attempt": args.attempt,
                "pr_head_sha": args.pr_head_sha,
                **_source_identity(),
            }
            head = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            if head != args.sha:
                raise ValueError("aggregate checkout differs from expected github.sha")
            summary = gate_artifacts(args.reports, expected, needs)
            rendered = json.dumps(summary, indent=2, sort_keys=True)
            print(rendered)
            if os.environ.get("GITHUB_STEP_SUMMARY"):
                with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
                    stream.write(
                        "## Backend Test Gate\n\n```json\n" + rendered + "\n```\n"
                    )
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"backend gate error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
