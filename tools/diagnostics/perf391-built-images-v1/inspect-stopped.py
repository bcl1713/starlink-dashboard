"""Extract only from unstarted task-owned containers. No exec/start/run path."""

import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
ROOT = Path("/tmp/perf391-build-408")
ledger = []


def command(*args):
    row = {"argv": ["docker", *args], "status": "intent"}
    ledger.append(row)
    save()
    t = time.monotonic()
    p = subprocess.run(
        ["timeout", "--kill-after=5s", "120s", "docker", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    row.update(
        exit=p.returncode,
        wall_seconds=time.monotonic() - t,
        stdout=p.stdout,
        stderr=p.stderr,
    )
    save()
    p.check_returncode()
    return p.stdout


def save():
    (EVIDENCE / "extraction-ledger.json").write_text(
        json.dumps(ledger, indent=2) + "\n"
    )


def extract(name, tag, copies):
    cid = command(
        "create",
        "--name",
        name,
        "--label",
        "perf391.owner=perf391-build-408",
        "--entrypoint",
        "/bin/false",
        tag,
    ).strip()
    try:
        for source, target in copies:
            target.parent.mkdir(parents=True, exist_ok=True)
            command("cp", cid + ":" + source, str(target))
        state = json.loads(command("inspect", cid))[0]
        assert state["State"]["Status"] == "created" and state["State"]["Pid"] == 0
        assert state["State"]["StartedAt"].startswith("0001-")
        (EVIDENCE / (name + ".container.json")).write_text(
            json.dumps(state, indent=2) + "\n"
        )
    finally:
        command("rm", cid)


for role in ["A", "C"]:
    for kind in ["backend", "frontend"]:
        tag = f"perf391-diag-408-{role.lower()}-{kind}:f9cf80bd"
        image = json.loads(command("image", "inspect", tag))
        (EVIDENCE / f"{role}-{kind}.image.json").write_text(
            json.dumps(image, indent=2) + "\n"
        )
        root = ROOT / f"{role}-{kind}"
        root.mkdir(exist_ok=True)
        if kind == "frontend":
            copies = [
                ("/usr/share/nginx/html", EVIDENCE / f"{role}-assets"),
                ("/etc/nginx/conf.d/default.conf", root / "nginx.conf"),
                ("/lib/apk/db/installed", root / "apk-installed"),
            ]
        elif role == "C":
            copies = [
                (s, root / t)
                for s, t in [
                    (
                        "/home/appuser/.local/lib/python3.11/site-packages",
                        "site-packages",
                    ),
                    ("/usr/local/lib/python3.11/site-packages", "global-site-packages"),
                    ("/var/lib/dpkg/status", "dpkg-status"),
                    ("/diagnostic", "diagnostic"),
                    ("/app", "app"),
                    ("/acceptance", "acceptance"),
                    ("/opt/customer-briefing/assets", "renderer-assets"),
                    ("/usr/local/bin/node", "node"),
                ]
            ]
        else:
            copies = [("/usr/local/bin/node", root / "node")]
        extract(f"perf391-build-408-{role.lower()}-{kind}", tag, copies)

for stage, path in [
    ("frontend-builder", "/workspace/frontend/mission-planner"),
    ("renderer-builder", "/renderer"),
]:
    tag = f"perf391-diag-408-{stage}:f9cf80bd"
    root = ROOT / stage
    root.mkdir()
    (EVIDENCE / (stage + ".image.json")).write_text(command("image", "inspect", tag))
    extract(
        "perf391-build-408-" + stage,
        tag,
        [
            (path + "/node_modules", root / "node_modules"),
            (path + "/package-lock.json", root / "package-lock.json"),
            ("/usr/local/lib/node_modules/npm/package.json", root / "npm-package.json"),
            ("/usr/local/bin/node", root / "node"),
        ],
    )
    command("image", "rm", tag)
