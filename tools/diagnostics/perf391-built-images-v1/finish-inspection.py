"""Final config-only image/host inspection. Never starts containers or services."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE / "evidence"
ROOT = Path("/tmp/perf391-build-408")
sys.path.insert(0, str(HERE.with_name("perf391-runtime-preparation-v1")))
import prepare
from launcher import launch_plan

ledger = []


def command(argv, env=None):
    p = subprocess.run(
        ["timeout", "--kill-after=5s", "60s", *argv],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    ledger.append(
        {"argv": argv, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    )
    prepare.write(E / "final-inspection-commands.json", ledger)
    p.check_returncode()
    return p.stdout


result = {
    "roles": {},
    "selectors": {
        k: os.environ.get(k)
        for k in ["DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR"]
    },
}
for role in ["A", "C"]:
    receipt = json.loads((E / ("built-" + role + ".json")).read_bytes())
    proposal = launch_plan(
        role,
        Path("/tmp/perf391-smoke-408-" + role.lower()),
        E / "runtime-build-plan.json",
        receipt,
    )
    env = {
        **os.environ,
        **proposal["env"],
        "PERF391_CONTEXT": str(ROOT / "contexts" / role),
    }
    dc = [
        "docker",
        "compose",
        "-p",
        "perf391-build-408",
        "-f",
        str(E / (role + ".compose.base.json")),
        "-f",
        str(E / (role + ".compose.override.json")),
        "config",
        "--format",
        "json",
    ]
    config = json.loads(command(dc, env))
    for service, kind in [
        ("starlink-location", "backend"),
        ("mission-planner", "frontend"),
    ]:
        assert config["services"][service]["image"] == receipt["images"][kind]["id"]
        image = json.loads(
            command(["docker", "image", "inspect", receipt["images"][kind]["id"]])
        )[0]
        assert image["Config"]["Labels"] == receipt["images"][kind]["labels"]
        assert image["RepoDigests"] == receipt["images"][kind]["repo_digests"]
    prepare.write(E / (role + ".compose.actual.rendered.json"), config)
    tag = f"perf391-diag-408-{role.lower()}-backend:f9cf80bd"
    name = f"perf391-build-408-{role.lower()}-python"
    cid = command(
        [
            "docker",
            "create",
            "--name",
            name,
            "--label",
            "perf391.owner=perf391-build-408",
            "--entrypoint",
            "/bin/false",
            tag,
        ]
    ).strip()
    try:
        for source, target in [
            ("/usr/local/include/python3.11/patchlevel.h", "patchlevel.h"),
            ("/usr/local/bin/python3.11", "python3.11"),
        ]:
            command(
                [
                    "docker",
                    "cp",
                    cid + ":" + source,
                    str(ROOT / (role + "-backend") / target),
                ]
            )
        state = json.loads(command(["docker", "inspect", cid]))[0]
        assert (
            state["State"]["Status"] == "created"
            and state["State"]["Pid"] == 0
            and state["State"]["StartedAt"].startswith("0001-")
        )
        prepare.write(E / (name + ".container.json"), state)
    finally:
        command(["docker", "rm", cid])
    header = ROOT / (role + "-backend") / "patchlevel.h"
    assert '#define PY_VERSION              "3.11.17"' in header.read_text()
    shutil.copyfile(header, E / (role + "-python-patchlevel.h"))
    shutil.copytree(
        ROOT / (role + "-backend") / "renderer-assets", E / (role + "-renderer-assets")
    )
    result["roles"][role] = {
        "python_version_from_image_header": "3.11.17",
        "python_binary_sha256": prepare.sha(ROOT / (role + "-backend") / "python3.11"),
        "python_header_sha256": prepare.sha(header),
        "config_rendered": True,
        "image_identity_rechecked": True,
    }
result["context"] = command(["docker", "context", "show"]).strip()
result["daemon"] = command(
    [
        "docker",
        "info",
        "--format",
        "{{.ID}} {{.Name}} {{.ServerVersion}} {{.Driver}} {{.CgroupVersion}}",
    ]
)
for kind, argv in [
    ("containers", ["docker", "ps", "-aq"]),
    ("networks", ["docker", "network", "ls", "-q"]),
    ("volumes", ["docker", "volume", "ls", "-q"]),
]:
    listing = command([*argv, "--filter", "label=perf391.owner=perf391-build-408"])
    assert listing.strip() == ""
    result[kind] = []
    listing = command(
        [*argv, "--filter", "label=com.docker.compose.project=perf391-build-408"]
    )
    assert listing.strip() == ""
result["all_actor_containers"] = command(
    ["docker", "ps", "-a", "--format", "{{json .}}"]
)
assert result["all_actor_containers"].strip() == ""
result["listeners"] = command(["ss", "-ltnp"])
result["actor_processes"] = command(
    ["ps", "-u", str(os.getuid()), "-o", "pid,ppid,pgid,lstart,args"]
)
result["buildkit_disk_usage"] = command(["docker", "buildx", "du"])
result["task_disk_usage_before_removal"] = command(["du", "-sb", str(ROOT), str(E)])
result["disk_availability"] = command(
    ["df", "-B1", str(ROOT), "/srv/forge-nvme/oracle/docker"]
)
result["actor_cpu_quota"] = (
    Path("/sys/fs/cgroup/user.slice/user-1002.slice/cpu.max").read_text().strip()
)
assert result["actor_cpu_quota"] == "1000000 100000"
for tag in [
    "perf391-diag-408-frontend-builder:f9cf80bd",
    "perf391-diag-408-renderer-builder:f9cf80bd",
]:
    assert command(["docker", "image", "ls", "-q", tag]).strip() == ""
prepare.write(E / "final-inspection.json", result)
print("Final image/config/host inventory passed; temporary contexts not yet removed.")
