"""Read-only actor-daemon image and task-resource audit; no mutations."""

import datetime
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BUILT = HERE.with_name("perf391-built-images-v1")


def run(*args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


report = {
    "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "docker_host": os.environ.get("DOCKER_HOST"),
    "context": run("docker", "context", "show"),
    "daemon": run("docker", "info", "--format", "{{.Name}} {{.ServerVersion}} {{json .SecurityOptions}}"),
    "projects": {}, "images": {},
}
for project in ("perf391-smoke-408-a", "perf391-smoke-408-c", "p391-net-20261023-1149", "perf391-preflight-contract"):
    resources = {}
    for kind in ("container", "network", "volume"):
        resources[kind] = run("docker", kind, "ls", "-q", "--filter", "label=com.docker.compose.project=" + project)
    assert not any(resources.values()), resources
    report["projects"][project] = resources
for role in ("A", "C"):
    receipt = json.loads((BUILT / f"evidence/built-{role}.json").read_bytes())
    for name, expected in receipt["images"].items():
        actual = json.loads(run("docker", "image", "inspect", expected["id"]))[0]
        assert actual["Id"] == expected["id"]
        assert actual["Config"]["Labels"] == expected["labels"]
        assert actual["RepoDigests"] == expected["repo_digests"]
        report["images"][f"{role}-{name}"] = {"id": actual["Id"], "labels_and_repo_digests_identical": True}
listeners = run("ss", "-ltnp").splitlines()
ports = (38080, 38081, 38082, 38083, 38180, 38181, 38182, 38183, 43891, 43892)
report["task_listeners"] = [line for line in listeners if any(f":{port} " in line for port in ports)]
assert not report["task_listeners"]
# Exclude only this audit and its direct ancestors, whose argv contains the task path.
ancestors = {os.getpid()}
pid = os.getppid()
while pid > 0 and pid not in ancestors:
    ancestors.add(pid)
    try:
        pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
    except FileNotFoundError:
        break
processes = run("ps", "-eo", "pid=,pgid=,args=").splitlines()
report["task_processes"] = [line for line in processes if int(line.split()[0]) not in ancestors
                            and any(token in line for token in (str(HERE.parents[2]), "perf391-network-offline-", "perf391-smoke-408-", "tmpjq657w06", "perf391-network-correction/tools/diagnostics/perf391-network-correction-v1/check.py"))]
assert not report["task_processes"], report["task_processes"]
report["temporary_roots"] = [str(p) for p in Path("/tmp").glob("perf391-network-offline-*")]
assert not report["temporary_roots"]
prereq = json.loads((HERE / 'evidence/process-prerequisite.json').read_text())
for row in (prereq,prereq['child']):
    proc = Path('/proc')/str(row['pid'])
    assert not proc.exists() or (proc/'stat').read_text().rsplit(')',1)[1].split()[19] != row['start_id']
report['prerequisite_processes_absent'] = True
report["cleanup_verified"] = True
(HERE / "evidence" / (__import__("sys").argv[1] + "-host-audit.json")).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
print(json.dumps(report, indent=2))
