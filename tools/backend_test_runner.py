"""Own and clean the processes and private stores of one reported backend run."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


def process(pid):
    try:
        # comm can contain whitespace and parentheses; fields after its last ')'.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {
            "pid": pid,
            "start": fields[19],
            "ppid": int(fields[1]),
            "pgid": int(fields[2]),
            "state": fields[0],
        }
    except (FileNotFoundError, ProcessLookupError):
        return None


def listening():
    result = set()
    for name in ("tcp", "tcp6"):
        for line in Path(f"/proc/net/{name}").read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == "0A":
                result.add(fields[9])
    return result


class OwnedRunner:
    def __init__(self, root, evidence, grace=10):
        self.root = Path(root).resolve()
        self.evidence = Path(evidence).resolve()
        if (
            self.root.exists()
            or self.root == self.evidence
            or self.root in self.evidence.parents
        ):
            raise ValueError("private root must be new and evidence must be outside it")
        self.evidence.mkdir(parents=True, exist_ok=True)
        if (self.evidence / "ownership.json").exists():
            raise ValueError("refusing to reuse ownership evidence")
        self.grace = grace
        self.owned = {}
        self.sockets = set()
        self.active_process = None
        self.deadline = time.monotonic() + 45 * 60 - 12
        self.data = {
            "runner": process(os.getpid()),
            "private_paths": [str(self.root)],
            "evidence": str(self.evidence),
            "commands": [],
            "owned": [],
            "cleanup": None,
            "fd_observations": [],
            "compose_projects": [],
            "volumes": [],
        }
        self.handlers = {}
        # Record ownership/path intentions before creating temporary resources.
        self.save()
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "subreaper setup failed")
        self.root.mkdir()

    def save(self):
        self.data["owned"] = list(self.owned.values())
        path = self.evidence / "ownership.json"
        temp = self.evidence / ".ownership.json.tmp"
        temp.write_text(json.dumps(self.data, indent=2) + "\n")
        os.replace(temp, path)

    def _sample_fds(self, item):
        """Resample a narrow exit/exec race without losing PID/start ownership."""
        until = time.monotonic() + 0.1
        observation = None
        started = time.monotonic()
        while True:
            current = process(item["pid"])
            if (
                current is None
                or current["start"] != item["start"]
                or current["state"] == "Z"
            ):
                if observation is not None:
                    observation.update(
                        resolution="exited", elapsed_seconds=time.monotonic() - started
                    )
                return
            try:
                sockets = set()
                for fd in Path(f"/proc/{item['pid']}/fd").iterdir():
                    try:
                        target = os.readlink(fd)
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    if target.startswith("socket:["):
                        sockets.add(target[8:-1])
            except (FileNotFoundError, ProcessLookupError):
                if observation is not None:
                    observation.update(
                        resolution="exited", elapsed_seconds=time.monotonic() - started
                    )
                return
            except PermissionError as error:
                if observation is None:
                    observation = {
                        "pid": item["pid"],
                        "start": item["start"],
                        "first_seen_at": time.time(),
                        "denials": 0,
                        "resolution": None,
                        "error": repr(error),
                    }
                    self.data["fd_observations"].append(observation)
                observation["denials"] += 1
                # Stat access is mandatory. Do not hide identity/ownership errors.
                current = process(item["pid"])
                if (
                    current is None
                    or current["start"] != item["start"]
                    or current["state"] == "Z"
                ):
                    observation.update(
                        resolution="exited", elapsed_seconds=time.monotonic() - started
                    )
                    return
                remaining = until - time.monotonic()
                if remaining <= 0:
                    observation.update(
                        resolution="persistent",
                        elapsed_seconds=time.monotonic() - started,
                    )
                    self.save()
                    raise
                time.sleep(min(0.01, remaining))
            else:
                # Do not attribute a replacement process's sockets to this owner.
                current = process(item["pid"])
                readable = (
                    current is not None
                    and current["start"] == item["start"]
                    and current["state"] != "Z"
                )
                if readable:
                    self.sockets.update(sockets)
                if observation is not None:
                    observation.update(
                        resolution="readable" if readable else "exited",
                        elapsed_seconds=time.monotonic() - started,
                    )
                return

    def discover(self, *, sample_fds=True):
        table = {}
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                item = process(int(entry.name))
                if item is not None:
                    table[item["pid"]] = item
        parents = {os.getpid()}
        while True:
            found = {pid for pid, item in table.items() if item["ppid"] in parents}
            if found <= parents:
                break
            parents |= found
        items = [table[pid] for pid in parents - {os.getpid()} if pid in table]
        # Register every descendant before optional observation can fail.
        for item in items:
            self.owned[(item["pid"], item["start"])] = item
        self.save()
        if sample_fds:
            for item in items:
                self._sample_fds(item)
            self.save()

    def survivors(self):
        result = []
        for pid, start in self.owned:
            current = process(pid)
            if current is not None and current["start"] == start:
                result.append(current)
        return result

    def reap(self):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break
            if self.active_process is not None and pid == self.active_process.pid:
                self.active_process.returncode = os.waitstatus_to_exitcode(status)

    def cleanup(self):
        # FD diagnostics must never prevent identity-verified termination/reaping.
        self.discover(sample_fds=False)
        # Discover again during both windows to catch children created in handlers.
        for sig, seconds in ((signal.SIGTERM, self.grace), (signal.SIGKILL, 2)):
            until = time.monotonic() + seconds
            while True:
                self.discover(sample_fds=False)
                for item in self.survivors():
                    current = process(item["pid"])
                    if (
                        current
                        and current["start"] == item["start"]
                        and current["state"] != "Z"
                    ):
                        try:
                            os.kill(item["pid"], sig)
                        except ProcessLookupError:
                            pass
                self.reap()
                if not self.survivors() or time.monotonic() >= until:
                    break
                time.sleep(0.02)
        self.discover(sample_fds=False)
        self.reap()
        survivors = self.survivors()
        listeners = sorted(self.sockets & listening())
        self.data["cleanup"] = {"survivors": survivors, "listeners": listeners}
        self.save()
        if survivors or listeners:
            raise RuntimeError(f"cleanup failed: {survivors=}, {listeners=}")

    def run(self, command, *, cwd, label, limit, env=None):
        if self.data["cleanup"] is not None:
            self.data["cleanup"] = None
        allowance = min(limit, self.deadline - time.monotonic())
        if allowance <= 0:
            raise SystemExit(124)
        record = {
            "label": label,
            "command": command,
            "cwd": str(cwd),
            "limit_seconds": allowance,
            "planned_at": time.time(),
            "pid": None,
            "pgid": None,
            "exit_code": None,
            "subprocess_returncode": None,
            "harness_error": None,
            "cleanup_error": None,
        }
        self.data["commands"].append(record)
        self.save()  # command ownership intention precedes Popen
        started = time.monotonic()
        proc = None
        result = None
        try:
            with (self.evidence / f"{label}.log").open("w") as log:
                proc = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                self.active_process = proc
                record.update(pid=proc.pid, pgid=proc.pid)
                item = process(proc.pid)
                if item:
                    self.owned[(proc.pid, item["start"])] = item
                self.save()
                while proc.poll() is None:
                    self.discover()
                    if time.monotonic() - started >= allowance:
                        result = 124
                        break
                    time.sleep(0.1)
                if result is None:
                    result = proc.returncode
        except BaseException as error:
            record["harness_error"] = repr(error)
            if isinstance(error, SystemExit):
                result = error.code if isinstance(error.code, int) else 1
            elif isinstance(error, KeyboardInterrupt):
                result = 130
            else:
                result = 1
            raise
        finally:
            try:
                # Optional FD observation errors cannot preempt owned cleanup.
                self.cleanup()
                if proc is not None:
                    proc.wait(timeout=2)
            except BaseException as error:
                record["cleanup_error"] = repr(error)
                if result is None or result == 0:
                    result = 1
                raise
            finally:
                status = result if result is not None else 1
                record.update(
                    exit_code=status if status >= 0 else 128 - status,
                    subprocess_returncode=proc.returncode if proc is not None else None,
                    elapsed_seconds=time.monotonic() - started,
                )
                self.active_process = None
                self.save()
        if result:
            raise SystemExit(result if result > 0 else 128 - result)

    def __enter__(self):
        def stop(signum, frame):
            raise SystemExit(128 + signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            self.handlers[sig] = signal.signal(sig, stop)
        return self

    def __exit__(self, exc_type, exc, tb):
        # Prevent a repeated signal from interrupting the bounded cleanup window.
        for sig in self.handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            self.cleanup()
            shutil.rmtree(self.root)
            self.data["private_paths_removed"] = True
            self.save()
        finally:
            for sig, handler in self.handlers.items():
                signal.signal(sig, handler)


def run_backend(repo, commands, *, report, run_root, shard=None):
    """Run canonical commands in one isolated checkout with recorded ownership."""
    from backend_ci import reject_pytest_overrides

    reject_pytest_overrides(os.environ)
    repo, report, run_root = Path(repo), Path(report), Path(run_root)
    if not report.is_absolute() or not run_root.is_absolute():
        raise ValueError("report and run-root must be absolute")
    if report.exists() or run_root.exists():
        raise ValueError("report and private root must be fresh")
    if report.parent == run_root or run_root in report.parents:
        raise ValueError("evidence must be outside the private root")
    lock = repo / ".backend-ci-active"
    # The atomic per-checkout claim rejects concurrent local shards; independent
    # worktrees and GitHub runner checkouts have separate claims.
    with lock.open("x") as stream:
        stream.write(
            json.dumps(
                {
                    "runner": process(os.getpid()),
                    "private_root": str(run_root),
                    "report": str(report),
                }
            )
            + "\n"
        )
    runner = None
    try:
        with OwnedRunner(run_root, report.parent, grace=5) as runner:
            # Also reserve cleanup inside the 20-minute command budget. The
            # boundary uses TERM5s plus KILL/reap2s to fit an early outer TERM's
            # 10-second kill grace; OwnedRunner's standalone default stays 10s.
            runner.deadline = time.monotonic() + 20 * 60 - 12
            runner.data["checkout"] = str(repo)
            runner.data["report"] = str(report)
            runner.data["shard"] = shard
            runner.data["checkout_claim"] = str(lock)
            runner.save()
            env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    [str(repo / "tools"), str(repo / "backend/starlink-location")]
                ),
                "STARLINK_TEST_DATA_DIR": str(runner.root / "bootstrap"),
                "STARLINK_DISABLE_BACKGROUND_TASKS": "1",
                "XDG_CACHE_HOME": str(runner.root / "cache"),
                "MPLCONFIGDIR": str(runner.root / "matplotlib"),
            }
            for index, (command, cwd) in enumerate(commands):
                command = list(command)
                label = "inventory" if index == 0 else "pytest"
                if "pytest" in command:
                    command += [
                        "-p",
                        "backend_ci",
                        f"--backend-ci-report={report}",
                        f"--basetemp={runner.root / 'basetemp'}",
                    ]
                    if shard:
                        command += [f"--backend-ci-shard={shard}"]
                try:
                    runner.run(
                        command,
                        cwd=cwd,
                        env=env,
                        label=label,
                        limit=180 if index == 0 else 1200,
                    )
                finally:
                    log = runner.evidence / f"{label}.log"
                    if log.exists():
                        print(log.read_text(), end="", flush=True)
    finally:
        if runner is None or runner.data.get("private_paths_removed") is True:
            lock.unlink(missing_ok=True)
