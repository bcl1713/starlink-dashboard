"""Run failure probes exclusively in the recorded project's disposable containers."""

import json
from pathlib import Path
from urllib.request import urlopen


def run_failure_suite(owner, *, origin: str) -> dict:
    name = f"{owner.project}-storage-failures"
    owner.ownership["containers"].append(name)
    owner.persist()
    source = (
        Path(owner.env["OPERATOR_SOURCE_ROOT"]) / "tools/acceptance/operator-journal"
    )
    image = owner.ownership["imageIdentity"]["backend"]["tag"]
    output = owner.execute(
        [
            "docker",
            "run",
            "--name",
            name,
            "--label",
            f"com.docker.compose.project={owner.project}",
            "--network",
            "none",
            "--user",
            "1000:1000",
            "--tmpfs",
            "/failure:rw,size=4m,uid=1000,gid=1000,mode=0700",
            "--mount",
            f"type=bind,src={source},dst=/acceptance,readonly",
            "--env",
            "PYTHONPATH=/acceptance:/app",
            "--entrypoint",
            "python",
            image,
            "/acceptance/store_probe.py",
        ],
        timeout=120,
    )
    result = json.loads(output.splitlines()[-1])
    for endpoint in (
        "/",
        "/missions",
        "/config",
        "/api/status",
        "/api/v2/operator/health",
    ):
        with urlopen(origin + endpoint, timeout=10) as response:
            assert response.status == 200
    result["baselinePagesAfterFailures"] = True
    (owner.root / "failures.json").write_text(json.dumps(result, indent=2))
    return result
