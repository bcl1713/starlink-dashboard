"""Read-only Forge inventory. No application HTTP, browser launch or capture."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path, limit=65536):
    try:
        with Path(path).open("rb") as f:
            raw = f.read(limit + 1)
        if len(raw) > limit:
            return {"unavailable": "file_limit"}
        return raw.decode()
    except OSError as error:
        return {"unavailable": type(error).__name__}


def command(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return {
            "argv": args,
            "exit": p.returncode,
            "stdout": p.stdout[:65536],
            "stderr": p.stderr[:4096],
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"argv": args, "unavailable": type(error).__name__}


def inventory():
    repo = Path(__file__).resolve().parents[3]
    # The primary installation is inspected; nothing is installed in this worktree.
    primary = Path("/home/oracle-worker/Work/starlink-dashboard")
    node_root = primary / "frontend/mission-planner"
    result = {
        "schema": "perf391-runtime-preflight-v1",
        "utc": time.strftime("%FT%TZ", time.gmtime()),
        "executor": {
            "uid": os.getuid(),
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "start_id": Path("/proc/self/stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()[19],
        },
        "mode": "read_only_inventory",
        "runtime_started": False,
        "selectors": {
            k: os.environ.get(k)
            for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR")
        },
        "policy_snapshot": read("/etc/codex/network-policy.json"),
        "environment_status_tool": "unavailable in this session",
        "repo": str(repo),
        "commands": {},
        "files": {},
        "namespaces": {},
    }
    commands = {
        "docker_context": ["docker", "context", "show"],
        "docker_endpoint": [
            "docker",
            "context",
            "inspect",
            "--format",
            "{{.Endpoints.docker.Host}}",
        ],
        "docker_info": [
            "docker",
            "info",
            "--format",
            "{{json .ServerVersion}} {{json .Driver}} {{json .CgroupDriver}} {{json .CgroupVersion}} {{json .NCPU}} {{json .MemTotal}} {{json .SecurityOptions}}",
        ],
        "compose": ["docker", "compose", "version"],
        "buildx": ["docker", "buildx", "version"],
        "images": [
            "docker",
            "image",
            "ls",
            "--no-trunc",
            "--digests",
            "--format",
            "{{.Repository}} {{.Tag}} {{.Digest}} {{.ID}}",
        ],
        "containers": [
            "docker",
            "ps",
            "--format",
            "{{.ID}} {{.Image}} {{.Names}} {{.Ports}}",
        ],
        "networks": [
            "docker",
            "network",
            "ls",
            "--format",
            "{{.ID}} {{.Name}} {{.Driver}}",
        ],
        "node": ["node", "--version"],
        "python": [sys.executable, "--version"],
        "python311": [
            "/home/oracle-worker/.local/share/uv/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11",
            "--version",
        ],
        "listeners": ["ss", "-ltn"],
        "addresses": ["ip", "-brief", "address"],
        "routes": ["ip", "route"],
        "capabilities": ["capsh", "--print"],
        "capture_file_caps": ["getcap", "/usr/bin/tcpdump"],
        "filesystem": ["df", "-B1", str(repo)],
        "processes": ["ps", "-u", str(os.getuid()), "-o", "pid,ppid,pgid,comm"],
    }
    for key, args in commands.items():
        result["commands"][key] = command(args)
    for path in (
        "/proc/self/cgroup",
        "/proc/self/status",
        "/proc/meminfo",
        "/proc/cpuinfo",
        "/proc/sys/kernel/random/boot_id",
        "/sys/fs/cgroup/cgroup.controllers",
    ):
        result["files"][path] = read(path)
    cgroup = read("/proc/self/cgroup")
    if isinstance(cgroup, str) and cgroup.startswith("0::/"):
        base = Path("/sys/fs/cgroup") / cgroup.strip()[3:].lstrip("/")
        for parent in [base, *list(base.parents)[:3]]:
            for name in (
                "cpu.max",
                "cpu.stat",
                "cpuset.cpus.effective",
                "memory.max",
                "memory.current",
                "pids.max",
                "cgroup.controllers",
                "io.stat",
            ):
                result["files"][str(parent / name)] = read(parent / name)
    for name in ("pid", "net", "mnt", "cgroup", "time"):
        try:
            result["namespaces"][name] = os.readlink("/proc/self/ns/" + name)
        except OSError as error:
            result["namespaces"][name] = {"unavailable": type(error).__name__}
    result["process_visibility"] = {
        p: read(p) for p in ("/proc/1/stat", "/proc/1/cgroup")
    }
    for label, path in (
        ("node", shutil.which("node")),
        ("tcpdump", "/usr/bin/tcpdump"),
    ):
        if path and Path(path).is_file():
            result[label + "_binary"] = {
                "path": str(Path(path).resolve()),
                "sha256": digest(path),
                "mode": oct(Path(path).stat().st_mode),
            }
    js = r"""
const {createRequire}=require('node:module');
const {readFileSync,existsSync}=require('node:fs');
const req=createRequire(process.argv[1]+'/package.json');
const core=require('node:path').dirname(req.resolve('playwright-core/package.json'));
const {chromium}=req('playwright');
const types=readFileSync(core+'/types/types.d.ts','utf8');
console.log(JSON.stringify({version:req('playwright/package.json').version,
  executable:chromium.executablePath(), executableExists:existsSync(chromium.executablePath()),
  addInitScriptDisposable:/addInitScript<Arg>[\s\S]{0,250}Promise<Disposable>/.test(types),
  exposeBindingDisposable:/exposeBinding\([^;]{0,250}Promise<Disposable>/.test(types),
  browsers:JSON.parse(readFileSync(core+'/browsers.json','utf8'))}));
"""
    pw = command(["node", "-e", js, str(node_root)])
    result["commands"]["playwright_inventory"] = pw
    if pw.get("exit") == 0:
        data = json.loads(pw["stdout"])
        result["playwright"] = data
        result["chromium_binary"] = {
            "path": data["executable"],
            "sha256": digest(data["executable"]),
        }
        result["commands"]["chromium_libraries"] = command(["ldd", data["executable"]])
    for key in ("package.json", "package-lock.json"):
        result[key] = {"path": str(node_root / key), "sha256": digest(node_root / key)}
    for kind in ("container", "network", "volume"):
        verb = ["ps", "-aq"] if kind == "container" else [kind, "ls", "-q"]
        result["commands"]["task_" + kind] = command(
            [
                "docker",
                *verb,
                "--filter",
                "label=com.docker.compose.project=perf391-prep-408",
            ]
        )
    return result


if __name__ == "__main__":
    print(json.dumps(inventory(), sort_keys=True, indent=2))
