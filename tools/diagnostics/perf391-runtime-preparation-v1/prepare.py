"""Offline source/context/Compose compiler. Never invokes Docker or application code."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INTEGRATION = HERE.with_name("perf391-diagnostic-integration-v1")
DELIVERY = "cd734117cb5580ef2579145c99d1cc30aeae9451"
TESTED = "051870c738d9ab72338852ea848918a35a663094"
RELEASE_HASH = "1ff9bf12f578538b6a2fb8946395f88993f569b1ec9aeb3939d4f27284601200"
sys.path.insert(0, str(INTEGRATION))
import build  # noqa: E402
import verify_frontend  # noqa: E402

PYTHON_BASE = "python:3.11-slim-trixie@sha256:b95327ce1439e687237841b0210677aeadd62d55a060a5f6bcb9c15bf6251dd3"
NODE_BASE = "node:22.22.2-trixie-slim@sha256:961a65354946a04bbf2bfb3a1b25b53638a0e1fdb07ff56689955b9788400903"
PROMETHEUS = "prom/prometheus:v3.5.0@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996"
NGINX = "nginx:alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d"
OVERLAY_FILES = (
    "prepare.py",
    "runtime_backend.proposed.py",
    "vite.perf391.mjs",
    "frontend.Dockerfile",
    "browser-owner.proposed.mjs",
    "browser-runtime.ts",
    "execute.proposed.py",
    "launcher.py",
    "analyze-runtime.py",
    "audit.py",
    "runtime-receipt-schema.json",
)
BACKEND_MODULES = (
    "backend_probe.py",
    "workers.py",
    "diagnostic_app.py",
    "contract.json",
)
NODE_MODULES = (
    "browser.mjs",
    "collect.mjs",
    "observer.mjs",
    "browser-probe.ts",
    "frontend-config.mjs",
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def verify_overlay(plan):
    actual = {name: sha(HERE / name) for name in OVERLAY_FILES}
    build.require(
        actual == plan["overlay_files"]
        and build.digest(build.canonical(actual)) == plan["overlay_sha256"],
        "runtime overlay drift",
    )


def browser_tree(installation, executable):
    files = {}
    roots = {
        "playwright": Path(installation) / "node_modules/playwright",
        "playwright-core": Path(installation) / "node_modules/playwright-core",
        "chromium": Path(executable).parent,
    }
    for kind, root in roots.items():
        build.require(
            root.is_dir() and not root.is_symlink(),
            "browser installation root unavailable",
        )
        for path in sorted(root.rglob("*")):
            build.require(
                not path.is_symlink(),
                "browser distribution symlink requires separate review",
            )
            if path.is_file():
                files[kind + "/" + path.relative_to(root).as_posix()] = {
                    "sha256": sha(path),
                    "bytes": path.stat().st_size,
                }
    return build.digest(build.canonical(files))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def check_release():
    release_path = INTEGRATION / "evidence/stage5/release-manifest.json"
    build.require(sha(release_path) == RELEASE_HASH, "Stage 5 release manifest drift")
    release = json.loads(release_path.read_bytes())
    actual = set()
    ignored = {"artifacts", "node_modules", "__pycache__", ".ruff_cache", "evidence"}
    for path in INTEGRATION.rglob("*"):
        relative = path.relative_to(INTEGRATION)
        if (path.is_file() or path.is_symlink()) and not ignored.intersection(
            relative.parts
        ):
            actual.add(relative.as_posix())
    build.require(
        actual == set(release["source_files"]), "Stage 5 source closure changed"
    )
    for name, expected in release["files"].items():
        path = INTEGRATION / name
        build.safe_path(name)
        build.require(
            not path.is_symlink()
            and INTEGRATION in path.resolve().parents
            and sha(path) == expected,
            "Stage 5 file drift: " + name,
        )
    # Runtime instrumentation is the exact tested source, not only a delivery claim.
    for name in release["source_files"]:
        # Reporting files changed after the tested source. Modules/configs/patches did not.
        if name.endswith((".py", ".mjs", ".ts", ".json", ".patch", ".txt")):
            recorded = build.git(
                REPO, "show", TESTED + ":" + str(INTEGRATION.relative_to(REPO) / name)
            )
            build.require(
                recorded == (INTEGRATION / name).read_bytes(),
                "tested source drift: " + name,
            )
    return {
        "release_manifest_sha256": RELEASE_HASH,
        "verified_files": len(release["files"]),
        "source_files": len(release["source_files"]),
    }


def labels(role, identity, overlay_hash):
    return {
        "diagnostic": "true",
        "org.opencontainers.image.revision": build.PINS[role],
        "base_application_sha": build.PINS[role],
        "integration_source_sha": TESTED,
        "collector_source_sha": build.PINS["collector"],
        "patch_sha256": sha(INTEGRATION / "patches" / (role + ".patch")),
        "effective_source_sha256": identity["effective_source_sha256"],
        "frontend_patch_sha256": identity["frontend_patch_sha256"],
        "collector_release_sha": build.PINS["release"],
        "frozen_harness_sha": build.PINS["harness"],
        "runtime_overlay_sha256": overlay_hash,
        "perf391.role": role,
    }


def compose(role):
    # A task-only base plus override; deliberately never merge production Compose.
    base = {
        "services": {
            "starlink-location": {
                "image": "${PERF391_BACKEND_IMAGE:?reviewed immutable diagnostic image required}",
                "pull_policy": "never",
            },
            "mission-planner": {
                "image": "${PERF391_FRONTEND_IMAGE:?reviewed immutable diagnostic image required}",
                "pull_policy": "never",
            },
            "prometheus": {"image": PROMETHEUS, "pull_policy": "never"},
        },
        "volumes": {name: {} for name in ("data", "routes", "metrics")},
        "networks": {"default": {"internal": False}},
    }
    common = {
        "restart": "no",
        "init": True,
        "pids_limit": 256,
        "logging": {"driver": "local", "options": {"max-size": "10m", "max-file": "1", "compress": "false"}},
        "stop_grace_period": "8s",
    }
    services = {
        "starlink-location": {
            **common,
            "cpus": 2,
            "mem_limit": "2g",
            "ports": ["127.0.0.1:${PERF391_BACKEND_PORT}:8000"],
            "environment": {
                "PYTHONPATH": "/diagnostic:/acceptance:/app",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PERF_SYNTHETIC": "1",
                "PERF391_ROLE": role,
                "PERF391_RUN": "${PERF391_RUN}",
                "STARLINK_MODE": "simulation",
                "SIMULATION_MODE": "true",
                "OPERATOR_ENABLED": "true",
                "OPERATOR_SIMULATION_RUN_ID": "default",
                "STARLINK_PROMETHEUS_URL": "http://prometheus:9090",
                "STARLINK_ROUTE_LATITUDE_START": "0",
                "STARLINK_ROUTE_LONGITUDE_START": "-10",
                "STARLINK_GROUND_ENTRY_LATITUDE": "0",
                "STARLINK_GROUND_ENTRY_LONGITUDE": "0",
                "NO_PROXY": "prometheus,localhost,127.0.0.1",
            },
            "volumes": ["data:/app/data", "routes:/data"],
            "healthcheck": {
                "test": [
                    "CMD",
                    "curl",
                    "--max-time",
                    "1",
                    "-f",
                    "http://localhost:8000/health",
                ],
                "interval": "2s",
                "timeout": "2s",
                "retries": 15,
                "start_period": "1s",
            },
        },
        "prometheus": {
            **common,
            "cpus": 1,
            "mem_limit": "1g",
            "ports": ["127.0.0.1:${PERF391_PROMETHEUS_PORT}:9090"],
            "volumes": [
                "metrics:/prometheus",
                "${PERF391_CONTEXT}/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro",
                "${PERF391_CONTEXT}/monitoring/prometheus/rules:/etc/prometheus/rules:ro",
                "${PERF391_OUTPUT}/history.openmetrics:/seed/history.openmetrics:ro",
            ],
            "command": [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.retention.time=12h",
                "--storage.tsdb.path=/prometheus",
            ],
        },
        "mission-planner": {
            **common,
            "cpus": 0.5,
            "mem_limit": "256m",
            "pids_limit": 64,
            "ports": ["127.0.0.1:${PERF391_FRONTEND_PORT}:80"],
            "depends_on": {"starlink-location": {"condition": "service_healthy"}},
        },
    }
    return base, {"services": services}


def prepare(output):
    output = Path(output).resolve()
    build.require(not output.exists(), "output must be a new task-owned path")
    release = check_release()
    build.verify_collector_release(REPO)
    overlay = {name: sha(HERE / name) for name in OVERLAY_FILES}
    overlay_hash = build.digest(build.canonical(overlay))
    output.mkdir(parents=True)
    write(
        output / "ownership.json",
        {
            "purpose": "offline context validation only",
            "paths": [str(output)],
            "runtime_resources": [],
            "cleanup": "remove this recorded output tree only",
        },
    )
    derivatives = verify_frontend.verify(REPO, output / "derivatives")
    result = {
        "schema": "perf391-runtime-build-plan-v1",
        "qualification": "offline_preparation_only",
        "runtime_authorized": False,
        "delivery": DELIVERY,
        "tested_source": TESTED,
        "pins": build.PINS,
        "release": release,
        "overlay_files": overlay,
        "overlay_sha256": overlay_hash,
        "platform": "linux/amd64",
        "bases": {
            "python": PYTHON_BASE,
            "node": NODE_BASE,
            "nginx": NGINX,
            "prometheus": PROMETHEUS,
        },
        "roles": {},
        "compiled_assets": None,
        "image_ids": None,
    }
    for role in ("A", "C"):
        identity = derivatives["roles"][role]
        context = output / role
        shutil.copytree(output / "derivatives" / (role + "-effective"), context)
        stage = context / ".perf391"
        stage.mkdir()
        diagnostic = stage / "diagnostic"
        diagnostic.mkdir()
        for name in (*BACKEND_MODULES, *NODE_MODULES):
            shutil.copyfile(INTEGRATION / name, diagnostic / name)
        shutil.copyfile(
            HERE / "runtime_backend.proposed.py", diagnostic / "runtime_backend.py"
        )
        shutil.copyfile(HERE / "browser-runtime.ts", diagnostic / "browser-runtime.ts")
        frozen = build.archive_files(
            build.git(
                REPO, "archive", "--format=tar", build.PINS["harness"], *build.FROZEN
            )
        )
        for path, (data, _mode) in frozen.items():
            relative = path.removeprefix("tools/acceptance/")
            alias = (
                relative.replace("performance/", "strict_performance/", 1)
                if relative.startswith("performance/")
                else relative.replace("performance_availability/", "performance/", 1)
            )
            target = stage / "acceptance" / alias
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        shutil.copytree(
            context / "tools/acceptance/operator-journal", stage / "acceptance/journal"
        )
        shutil.copyfile(HERE / "vite.perf391.mjs", stage / "vite.perf391.mjs")
        write(
            stage / "tsconfig.perf391.json",
            {
                "extends": "./tsconfig.app.json",
                "compilerOptions": {
                    "incremental": False,
                    "paths": {
                        "@/*": ["./src/*"],
                        "@perf391/browser-probe": ["/diagnostic/browser-runtime.ts"],
                    },
                },
            },
        )
        runtime_frontend_closure = build.digest(
            build.canonical(
                {
                    "frontend_tree_sha256": identity["frontend_tree_sha256"],
                    "frontend_probe": sha(INTEGRATION / "browser-probe.ts"),
                    "frontend_config": sha(INTEGRATION / "frontend-config.mjs"),
                    "alias": sha(HERE / "browser-runtime.ts"),
                    "vite": sha(HERE / "vite.perf391.mjs"),
                    "typescript": sha(stage / "tsconfig.perf391.json"),
                    "recipe": sha(HERE / "frontend.Dockerfile"),
                }
            )
        )
        role_labels = labels(role, identity, overlay_hash)
        role_labels["runtime_frontend_closure_sha256"] = runtime_frontend_closure
        suffix = (
            "\n"
            + "\n".join(
                "LABEL " + k + "=" + json.dumps(v) for k, v in role_labels.items()
            )
            + "\n"
        )
        original = (context / "backend/starlink-location/Dockerfile").read_text()
        backend = original.replace(
            "FROM node:22.22.2-trixie-slim AS renderer-build",
            "FROM " + NODE_BASE + " AS renderer-build",
        )
        backend = backend.replace("FROM python:3.11-slim-trixie", "FROM " + PYTHON_BASE)
        build.require(backend.count("@sha256:") == 3, "unexpected backend FROM layout")
        backend += "\nCOPY .perf391/diagnostic/ /diagnostic/\nCOPY .perf391/acceptance/ /acceptance/\n"
        backend += "RUN install -d -m 0755 -o appuser -g appuser /app/data/perf391\n"
        backend += (
            "ENV PYTHONPATH=/diagnostic:/acceptance:/app PYTHONDONTWRITEBYTECODE=1\n"
        )
        backend += 'CMD ["uvicorn", "runtime_backend:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "5"]\n'
        (stage / "backend.Dockerfile").write_text(backend + suffix)
        (stage / "frontend.Dockerfile").write_text(
            (HERE / "frontend.Dockerfile").read_text() + suffix
        )
        for name in ("base", "override"):
            base, override = compose(role)
            write(
                output / (role + ".compose." + name + ".json"),
                base if name == "base" else override,
            )
        source_modules = {
            n: sha(INTEGRATION / n) for n in (*BACKEND_MODULES, *NODE_MODULES)
        }
        frontend_files = {
            name: record
            for name, record in json.loads(
                (output / "derivatives" / (role + "-files.json")).read_bytes()
            ).items()
            if name.startswith("frontend/")
        }
        result["roles"][role] = {
            "identity": identity,
            "labels": role_labels,
            "runtime_frontend_closure_sha256": runtime_frontend_closure,
            "diagnostic_modules": source_modules,
            "frontend_files_sha256": build.digest(build.canonical(frontend_files)),
            "package_lock_sha256": sha(
                context / "frontend/mission-planner/package-lock.json"
            ),
            "requirements_sha256": sha(
                context / "backend/starlink-location/requirements.txt"
            ),
            "context_sha256": build.tree_manifest(context)["tree_sha256"],
            "overlay_inventory": build.tree_manifest(stage),
            "compose_sha256": {
                n: sha(output / (role + ".compose." + n + ".json"))
                for n in ("base", "override")
            },
        }
    write(output / "runtime-build-plan.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(
        json.dumps(
            {
                "roles": list(result["roles"]),
                "release": result["release"],
                "runtime_authorized": False,
            }
        )
    )
