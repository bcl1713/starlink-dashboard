"""Read-only Forge image/resource audit. Never creates or starts resources."""

import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BUILT = HERE.with_name("perf391-built-images-v1") / "evidence"


def command(*args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


result = {"images": {}, "docker": {}, "process_survivors": [], "listeners": []}
for role in ("A", "C"):
    receipt = json.loads((BUILT / f"built-{role}.json").read_bytes())
    for kind, expected in receipt["images"].items():
        actual = json.loads(command("docker", "image", "inspect", expected["id"]))[0]
        assert actual["Id"] == expected["id"]
        assert actual["Config"]["Labels"] == expected["labels"]
        assert actual["RepoDigests"] == expected["repo_digests"]
        result["images"][role + "-" + kind] = actual["Id"]
for project in ("perf391-logging-fix", "perf391-smoke-408-a", "perf391-smoke-408-c"):
    result["docker"][project] = {}
    for kind, argv in (
        ("containers", ("ps", "-aq")),
        ("networks", ("network", "ls", "-q")),
        ("volumes", ("volume", "ls", "-q")),
    ):
        values = command(
            "docker", *argv, "--filter", "label=com.docker.compose.project=" + project
        ).splitlines()
        result["docker"][project][kind] = values
        assert not values, (project, kind, values)
# Exclude this audit and its invoking shell/timeout/exec ancestors only.
ancestors = set()
pid = os.getpid()
while pid > 0 and pid not in ancestors:
    ancestors.add(pid)
    try:
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError):
        break
for path in Path("/proc").glob("[0-9]*"):
    if int(path.name) in ancestors:
        continue
    try:
        cmd = (
            (path / "cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode(errors="replace")
        )
    except OSError:
        continue
    if any(
        marker in cmd
        for marker in (
            "/tmp/perf391-logging-",
            ".worktrees/perf391-logging-fix",
            "perf391-logging-check-",
        )
    ):
        result["process_survivors"].append({"pid": int(path.name), "command": cmd})
for line in command("ss", "-H", "-ltnp").splitlines():
    fields = line.split()
    if len(fields) > 3 and fields[3].rsplit(":", 1)[-1] in {
        str(p) for p in (*range(38080, 38084), *range(38180, 38184))
    }:
        result["listeners"].append(line)
assert not result["process_survivors"], result["process_survivors"]
assert not result["listeners"], result["listeners"]
assert not Path("/tmp/perf391-logging-fix").exists()
assert not list(Path("/tmp").glob("perf391-logging-check-*"))
result["temporary_root_removed"] = "/tmp/perf391-logging-fix"
result["clean"] = True
(HERE / "evidence/cleanup.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n"
)
print(
    "Four accepted image IDs/labels/digests unchanged; no owned processes, listeners or Docker resources; task temporary paths removed."
)
