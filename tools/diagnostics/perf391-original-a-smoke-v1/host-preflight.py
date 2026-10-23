"""Read-only host/image/cleanup inventory; creates no runtime resources."""

import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
offline = json.loads((HERE / "evidence/offline-preflight.json").read_bytes())
result = {"runtime_resources_created": False, "hostname": os.uname().nodename, "commands": [], "images": {}}


def command(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    row = {"argv": argv, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    result["commands"].append(row)
    assert p.returncode == 0, row
    return p.stdout


command(["docker", "context", "show"])
command(["docker", "info", "--format", "{{.Name}} {{.NCPU}} {{.MemTotal}} {{.CgroupVersion}}"])
for role, receipt in offline["receipts"].items():
    for kind, image in receipt["images"].items():
        actual = json.loads(command(["docker", "image", "inspect", image["id"], "--format", "{{json .}}"] ))
        assert actual["Id"] == image["id"]
        assert all(actual["Config"]["Labels"].get(k) == v for k, v in image["labels"].items())
        result["images"][role + "-" + kind] = {"id": actual["Id"], "labels_verified": True}
for kind in ("container", "network", "volume"):
    argv = ["docker", "ps", "-aq"] if kind == "container" else ["docker", kind, "ls", "-q"]
    for role in ("a", "c"):
        output = command([*argv, "--filter", "label=com.docker.compose.project=perf391-smoke-408-" + role])
        assert not output.strip(), output
listeners = command(["ss", "-ltn"])
assert not any(":" + str(port) + " " in listeners for port in range(38080, 38084))
command(["df", "-B1", str(HERE)])
result["process_identity"] = {"pid": os.getpid(), "pgid": os.getpgrp(), "pid_namespace": os.readlink("/proc/self/ns/pid")}
result["memory"] = Path("/proc/meminfo").read_text()
result["cgroup"] = Path("/proc/self/cgroup").read_text()
result["cleanup"] = "No runtime owner, child worker, container, network, volume or listener created; A/C project listings and A ports empty. Inventory subprocesses completed synchronously."
(HERE / "evidence/host-preflight.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print("Four retained image IDs/labels verified; no smoke project resources or A listeners.")
