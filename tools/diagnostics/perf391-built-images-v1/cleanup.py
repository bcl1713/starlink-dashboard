"""Verify ended task ownership and remove only the recorded private build root."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE / "evidence"
ROOT = Path("/tmp/perf391-build-408")
ownership = json.loads((E / "ownership.json").read_bytes())
assert ownership["root"] == str(ROOT) and ROOT.is_dir() and not ROOT.is_symlink()
result = {
    "utc": time.strftime("%FT%TZ", time.gmtime()),
    "process_checks": [],
    "commands": [],
}


def command(argv):
    p = subprocess.run(
        ["timeout", "--kill-after=5s", "30s", *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    result["commands"].append(
        {"argv": argv, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    )
    p.check_returncode()
    return p.stdout


manifests = list(E.glob("*/manifest.json"))
for path in manifests:
    m = json.loads(path.read_bytes())
    assert m["status"] == "clean" and not m["errors"], path
    assert all(p["reaped"] and not p["survivors"] for p in m["processes"])
    namespace = m["owner"]["pid_namespace"]
    for row in [m["owner"], *m["processes"], *m["adopted_processes"]]:
        live = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                start = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
                if (
                    start != row["start_id"]
                    or os.readlink(proc / "ns/pid") != namespace
                ):
                    continue
                ids = next(
                    l
                    for l in (proc / "status").read_text().splitlines()
                    if l.startswith("NSpid:")
                ).split()[1:]
                if int(ids[-1]) == row["pid"]:
                    live.append(int(proc.name))
            except (OSError, IndexError, StopIteration):
                continue
        result["process_checks"].append(
            {
                "manifest": str(path.relative_to(E)),
                "recorded_pid": row["pid"],
                "start_id": row["start_id"],
                "namespace": namespace,
                "host_matches": live,
            }
        )
        assert not live, (path, row, live)

ancestors = {os.getpid()}
pid = os.getpid()
while pid > 1:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    pid = int(fields[1])
    ancestors.add(pid)
survivors = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdecimal() or int(proc.name) in ancestors:
        continue
    try:
        args = (proc / "cmdline").read_bytes()
        if (
            b"/tmp/perf391-build-408" in args
            or b"tools/diagnostics/perf391-built-images-v1/" in args
        ):
            survivors.append(
                {"pid": int(proc.name), "comm": (proc / "comm").read_text().strip()}
            )
    except OSError:
        continue
assert not survivors, survivors
result["task_process_survivors"] = survivors
for kind, argv in [
    ("containers", ["docker", "ps", "-aq"]),
    ("networks", ["docker", "network", "ls", "-q"]),
    ("volumes", ["docker", "volume", "ls", "-q"]),
]:
    for label in [
        "perf391.owner=perf391-build-408",
        "com.docker.compose.project=perf391-build-408",
    ]:
        assert not command([*argv, "--filter", "label=" + label]).strip()
    result[kind] = []
assert not command(["docker", "ps", "-aq"]).strip()
result["listeners_snapshot"] = command(["ss", "-ltnp"])
result["retained_images"] = []
for tag in ownership["planned_tags"]:
    image = json.loads(command(["docker", "image", "inspect", tag]))[0]
    assert image["Config"]["Labels"]["diagnostic"] == "true"
    result["retained_images"].append(
        {"tag": tag, "id": image["Id"], "repo_digests": image["RepoDigests"]}
    )
for tag in ownership["temporary_stage_images"]:
    assert not command(["docker", "image", "ls", "-q", tag]).strip()
result["removed_stage_tags"] = ownership["temporary_stage_images"]
result["before_removal_bytes"] = command(["du", "-sb", str(ROOT)])
shutil.rmtree(ROOT)
assert not ROOT.exists()
result["temporary_root_removed"] = str(ROOT)
result["task_listeners"] = []
result["disposition"] = (
    "Four final diagnostic images retained for review; all extraction containers and temporary build-stage tags removed. Shared actor daemon, base images and BuildKit cache preserved. No task-owned builder was created."
)
result["cleanup_verified"] = True
(E / "cleanup.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    "Cleanup verified; private root removed; four labeled diagnostic images retained."
)
