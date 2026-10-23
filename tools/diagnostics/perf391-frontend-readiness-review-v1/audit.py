"""Read-only Forge audit for the frontend investigation; never start services."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HISTORY = HERE.with_name("perf391-a-approved-smoke-v1") / "evidence"


def command(argv):
    return subprocess.check_output(argv, text=True, timeout=10).strip()


def audit():
    assert Path("/proc/1/comm").read_text().strip() == "systemd"
    assert os.getuid() == 1002
    report = {
        "utc": time.strftime("%FT%TZ", time.gmtime()),
        "actor_uid": os.getuid(),
        "pid_namespace": os.readlink("/proc/self/ns/pid"),
        "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
        "docker_context": command(["docker", "context", "show"]),
        "docker_security_options": json.loads(
            command(["docker", "info", "--format", "{{json .SecurityOptions}}"])
        ),
        "docker": {},
        "images": {},
        "process_survivors": [],
        "process_scan_scope": "recorded historical identities and actor UID 1002 processes",
        "cwd_unreadable": [],
        "listeners": [],
        "temporary_paths_present": [],
        "task_runtime_resources_started": [],
        "source_sha256": {},
    }
    assert "name=rootless" in report["docker_security_options"]
    for role in ("a", "c"):
        project = "perf391-smoke-408-" + role
        report["docker"][project] = {}
        for kind, argv in (
            ("containers", ["docker", "ps", "-aq"]),
            ("networks", ["docker", "network", "ls", "-q"]),
            ("volumes", ["docker", "volume", "ls", "-q"]),
        ):
            report["docker"][project][kind] = command(
                [*argv, "--filter", "label=com.docker.compose.project=" + project]
            ).splitlines()
        receipt = json.loads(
            (HERE.with_name("perf391-built-images-v1") / f"evidence/built-{role.upper()}.json").read_bytes()
        )
        for kind, image in receipt["images"].items():
            actual = json.loads(command(["docker", "image", "inspect", image["id"], "--format", "{{json .}}"]))
            assert actual["Id"] == image["id"]
            assert actual["Config"]["Labels"] == image["labels"]
            assert actual["RepoDigests"] == image["repo_digests"]
            report["images"][role.upper() + "-" + kind] = image["id"]
    historical = json.loads((HISTORY / "final-host-cleanup.json").read_bytes())
    identities = {(r["pid"], r["start_id"]) for r in historical["checked_process_identities"]}
    report["historical_process_identities_checked"] = len(identities)
    ancestors = set()
    pid = os.getpid()
    while pid > 0 and pid not in ancestors:
        ancestors.add(pid)
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    markers = (str(REPO), "/tmp/perf391-a-approved-smoke", "/tmp/perf391-smoke-408-a", "/tmp/perf391-smoke-408-c")
    for path in Path("/proc").glob("[0-9]*"):
        if int(path.name) in ancestors:
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            if (int(path.name), fields[19]) in identities:
                report["process_survivors"].append({"pid": int(path.name), "start_id": fields[19]})
            if path.stat().st_uid != os.getuid():
                continue
            cmd = (path / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            try:
                cwd = os.readlink(path / "cwd")
            except PermissionError:
                cwd = ""
                report["cwd_unreadable"].append(int(path.name))
            if (int(path.name), fields[19]) in identities or any(m in cmd or cwd.startswith(m) for m in markers):
                report["process_survivors"].append({"pid": int(path.name), "start_id": fields[19], "command": cmd, "cwd": cwd})
        except FileNotFoundError:
            continue
    ports = set(range(38080, 38084)) | set(range(38180, 38184))
    report["ports_checked"] = sorted(ports)
    for line in command(["ss", "-H", "-ltnp"]).splitlines():
        fields = line.split()
        if len(fields) > 3 and fields[3].rsplit(":", 1)[-1] in {str(p) for p in ports}:
            report["listeners"].append(line)
    report["temporary_paths_present"] = [p for p in historical["removed_paths"] if Path(p).exists()]
    for name in (
        "perf391-runtime-preparation-v1/execute.proposed.py",
        "perf391-runtime-preparation-v1/launcher.py",
        "perf391-runtime-preparation-v1/browser-owner.proposed.mjs",
        "perf391-diagnostic-integration-v1/owner.py",
        "perf391-a-approved-smoke-v1/evidence/executor-launch-A.json",
    ):
        report["source_sha256"][name] = hashlib.sha256((HERE.parent / name).read_bytes()).hexdigest()
    report["clean"] = not (
        report["process_survivors"] or report["listeners"] or report["temporary_paths_present"]
        or any(rows for project in report["docker"].values() for rows in project.values())
    )
    return report


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["clean"] else 1)
