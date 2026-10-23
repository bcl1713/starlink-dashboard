"""Offline regeneration and full effective-Compose comparison; never starts services."""

import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
COMPARISON = HERE.with_name("perf391-a-functional-smoke-v1")
sys.path.insert(0, str(COMPARISON))
from comparison import regenerate, validate_compose, prepare, BUILT


def main():
    evidence = HERE / "evidence"
    # Record ownership before allocating scratch space; no runtime project is created.
    prepare.write(evidence / "ownership.json", {
        "purpose": "offline regeneration, tests and Compose config only",
        "pid": os.getpid(), "pgid": os.getpgid(0),
        "temporary_prefix": "perf391-network-offline-",
        "runtime_resources": [],
        "cleanup": "TemporaryDirectory exit cleanup; no services created",
    })
    with tempfile.TemporaryDirectory(prefix="perf391-network-offline-") as tmp:
        task = Path(tmp)
        generated, comparison = regenerate(task)
        context = task / "context"
        prepare.write(evidence / "comparison.json", comparison)
        report = {
            "scope": "offline only; no runtime qualification",
            "original_plan_sha256": prepare.sha(BUILT / "evidence/runtime-build-plan.json"),
            "original_regeneration_byte_identical": True,
            "python_version": sys.version,
            "compose_version": subprocess.check_output(["docker", "compose", "version"], text=True, timeout=10).strip(),
            "source_hashes": {}, "roles": {},
        }
        for path in [prepare.HERE / "prepare.py", prepare.HERE / "runtime_identity.py",
                     prepare.HERE / "network-overlay.json", COMPARISON / "comparison.py"]:
            report["source_hashes"][str(path.relative_to(prepare.REPO))] = prepare.sha(path)
        for role in ("A", "C"):
            launch, rendered = validate_compose(role, context, comparison)
            for kind in ("base", "override"):
                prepare.write(evidence / f"{role}.compose.{kind}.json", launch["compose"][kind])
            prepare.write(evidence / f"{role}.compose.json", rendered)
            services = rendered["services"]
            assert set(rendered["networks"]) == {"default"}
            assert not rendered["networks"]["default"].get("internal", False)
            for service in services.values():
                assert service["networks"] == {"default": None}
                assert all(port["host_ip"] == "127.0.0.1" for port in service["ports"])
            receipt = BUILT / f"evidence/built-{role}.json"
            report["roles"][role] = {
                "receipt_sha256": prepare.sha(receipt),
                "effective_source_sha256": generated["roles"][role]["identity"]["effective_source_sha256"],
                "context_sha256": generated["roles"][role]["context_sha256"],
                "compose_hashes": {kind: prepare.sha(evidence / f"{role}.compose{suffix}.json")
                                   for kind, suffix in (("base", ".base"), ("override", ".override"), ("rendered", ""))},
                "limits": {name: {key: service[key] for key in ("cpus", "mem_limit", "pids_limit", "logging")}
                           for name, service in services.items()},
                "loopback_ports": {name: service["ports"] for name, service in services.items()},
                "only_default_network": True,
                "images": {name: service["image"] for name, service in services.items()},
                "deadlines": launch["deadlines"],
            }
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PERF391_OFFLINE_ROOT": str(context)}
        selections = [(name.removeprefix("test_"), prepare.HERE, name + ".py") for name in
                      ("test_preparation", "test_node_identity", "test_logging", "test_frontend_readiness")]
        selections.append(("comparison", COMPARISON, "test_comparison.py"))
        for name, directory, pattern in selections:
            result = subprocess.run(["timeout", "--kill-after=10s", "2m", sys.executable, "-B", "-m", "unittest", "discover",
                                     "-s", str(directory), "-p", pattern, "-v", *(["-k", "ReadinessTests"] if name == "frontend_readiness" else [])],
                                    env=env, capture_output=True, timeout=140)
            (evidence / f"{name}-tests.log").write_bytes(result.stdout + result.stderr)
            assert result.returncode == 0, (name, result.stderr.decode())
        report["tests"] = {name: "passed; see " + name + "-tests.log" for name, _, _ in selections}
        report["earlier_broad_test_timeout"] = "Fake executor cleanup and readiness process-owner cases each reached 120s; process trees absent; owned scratch directories removed; timeout logs/owner evidence retained. Final readiness selection is deterministic ReadinessTests only."
        # Rendered paths intentionally retain the exact temporary context provenance.
        report["temporary_root"] = tmp
    report["temporary_root_absent"] = not Path(tmp).exists()
    assert report["temporary_root_absent"]
    prepare.write(evidence / "verification.json", report)
    print(json.dumps(report, indent=2))


def stop(signum, _frame):
    raise SystemExit(128 + signum)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    main()
