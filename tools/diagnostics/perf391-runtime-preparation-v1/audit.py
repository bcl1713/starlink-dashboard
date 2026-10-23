"""Read-only post-run host audit. Never signals or deletes a resource."""

import argparse
import json
import os
from pathlib import Path
import subprocess

from prepare import write


def audit(root):
    root = Path(root).resolve()
    launch = json.loads((root / "launch.json").read_bytes())
    project = launch["project"]
    if (
        project not in ("perf391-smoke-408-a", "perf391-smoke-408-c")
        or str(root) != launch["root"]
    ):
        raise ValueError("task ownership identity")
    report = {
        "schema": "perf391-runtime-cleanup-audit-v1",
        "project": project,
        "runtime_root": str(root),
        "unavailable": [],
        "docker": {},
        "processes": [],
        "listeners": [],
    }
    for kind, argv in (
        ("containers", ["docker", "ps", "-aq"]),
        ("networks", ["docker", "network", "ls", "-q"]),
        ("volumes", ["docker", "volume", "ls", "-q"]),
    ):
        result = subprocess.run(
            [*argv, "--filter", "label=com.docker.compose.project=" + project],
            capture_output=True,
            text=True,
            timeout=5,
        )
        report["docker"][kind] = result.stdout.split()
        if result.returncode:
            report["unavailable"].append(kind + ":" + result.stderr[:256])
    rows = []
    for name in (
        "manifest.json",
        "verification-owner/manifest.json",
        "cleanup-owner/manifest.json",
    ):
        manifest = json.loads((root / name).read_bytes())
        rows.append(manifest["owner"])
        rows.extend(manifest["processes"])
        rows.extend(manifest["adopted_processes"])
    browser = root / "browser/browser-process.json"
    if browser.exists():
        rows.append(json.loads(browser.read_bytes()))
    groups = {
        row["pgid"]
        for row in rows
        if row.get("pgid") and row.get("pid") == row.get("pgid")
    }
    identities = {
        (row["pid"], row["start_id"])
        for row in rows
        if row.get("pid") and row.get("start_id")
    }
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            pid, group, start = int(path.name), int(fields[2]), fields[19]
            if pid != os.getpid() and ((pid, start) in identities or group in groups):
                report["processes"].append(
                    {"pid": pid, "pgid": group, "start_id": start, "state": fields[0]}
                )
        except (OSError, IndexError):
            continue
    result = subprocess.run(["ss", "-ltn"], capture_output=True, text=True, timeout=5)
    if result.returncode:
        report["unavailable"].append("host listener visibility")
    for line in result.stdout.splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 4:
            port = columns[3].rsplit(":", 1)[-1]
            if port.isdecimal() and int(port) in launch["ownership"]["ports"]:
                report["listeners"].append(line)
    report["temporary_paths"] = (
        [str(p) for p in (root / "tmp").rglob("*")] if (root / "tmp").exists() else []
    )
    report["clean"] = not (
        report["unavailable"]
        or any(report["docker"].values())
        or report["processes"]
        or report["listeners"]
        or report["temporary_paths"]
    )
    write(root / "cleanup-audit.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.runtime)["clean"] else 1)
