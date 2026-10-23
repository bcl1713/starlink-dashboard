"""Offline qualification of extracted images; no application imports or launches."""

import json
import re
import shutil
import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE / "evidence"
ROOT = Path("/tmp/perf391-build-408")
sys.path.insert(0, str(HERE.with_name("perf391-runtime-preparation-v1")))
import prepare
from launcher import validate_receipt


def write(name, data):
    prepare.write(E / name, data)


def files(root):
    result = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            assert not p.is_symlink(), p
            result[p.relative_to(root).as_posix()] = prepare.sha(p)
    return result


def inventory(root):
    found = {}
    for dirname in ["global-site-packages", "site-packages"]:
        for d in distributions(path=[str(root / dirname)]):
            found[re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower()] = {
                "name": d.metadata["Name"],
                "version": d.version,
            }
    return [found[k] for k in sorted(found)]


plan_path = E / "runtime-build-plan.json"
plan = json.loads(plan_path.read_bytes())
prepare.verify_overlay(plan)
release = prepare.check_release()
reference = (E / "reference-python-packages.json").read_bytes()
assert (
    prepare.build.digest(reference)
    == "03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40"
)
summary = {
    "schema": "perf391-built-image-qualification-v1",
    "starting_commit": "f9cf80bd4fe7915863cf7e0ed5a6bc52616c377b",
    "runtime_executed": False,
    "release": release,
    "roles": {},
    "node_build_stages": {},
}

for stage in ["frontend-builder", "renderer-builder"]:
    root = ROOT / stage
    lock = json.loads((root / "package-lock.json").read_bytes())
    installed = json.loads((root / "node_modules/.package-lock.json").read_bytes())
    actual = {}
    for name, item in installed["packages"].items():
        package = root / name / "package.json"
        data = json.loads(package.read_bytes())
        assert (
            data["version"] == item["version"] == lock["packages"][name]["version"]
        ), name
        assert item.get("integrity") == lock["packages"][name].get("integrity"), name
        actual[name] = {
            "name": data["name"],
            "version": data["version"],
            "package_json_sha256": prepare.sha(package),
            "lock_integrity": item.get("integrity"),
        }
    write(stage + "-node-packages.json", actual)
    shutil.copyfile(
        root / "node_modules/.package-lock.json",
        E / (stage + "-installed-package-lock.json"),
    )
    assert (
        prepare.sha(root / "package-lock.json")
        == plan["roles"]["A"]["package_lock_sha256"]
    )
    version = subprocess.check_output(
        [str(root / "node"), "--version"], text=True
    ).strip()
    assert version == "v22.22.2"
    summary["node_build_stages"][stage] = {
        "packages": len(actual),
        "node_version": version,
        "node_sha256": prepare.sha(root / "node"),
        "npm_version": json.loads((root / "npm-package.json").read_bytes())["version"],
        "package_lock_sha256": prepare.sha(root / "package-lock.json"),
        "installed_package_lock_sha256": prepare.sha(
            root / "node_modules/.package-lock.json"
        ),
        "package_inventory_sha256": prepare.sha(E / (stage + "-node-packages.json")),
    }

pw_root = Path("/home/oracle-worker/Work/starlink-dashboard/frontend/mission-planner")
preflight = json.loads((E / "preflight-before.json").read_bytes())
executable = Path(preflight["playwright"]["executable"])
browser_tree = prepare.browser_tree(pw_root, executable)
browser = {
    "playwright": "1.63.0",
    "chromium_sha256": prepare.sha(executable),
    "node_sha256": prepare.sha(ROOT / "node/node"),
    "node_version": "22.22.2",
    "playwright_root": str(pw_root),
    "chromium_executable": str(executable),
}
assert (
    json.loads((pw_root / "node_modules/playwright/package.json").read_bytes())[
        "version"
    ]
    == "1.63.0"
)
write(
    "browser-filesystem-identity.json",
    {
        "browser": browser,
        "browser_tree_sha256": browser_tree,
        "launch_tested": False,
        "lane": "Filesystem identities only. Private 22.22.2 Node is the diagnostic build lane; historical browser benchmark Node 22.12.0 remains separate and untouched.",
    },
)

for role in ["A", "C"]:
    root = ROOT / (role + "-backend")
    context = ROOT / "contexts" / role
    assert (
        prepare.build.tree_manifest(context)["tree_sha256"]
        == plan["roles"][role]["context_sha256"]
    )
    packages = inventory(root)
    package_bytes = (json.dumps(packages) + "\n").encode()
    assert len(packages) == 89 and package_bytes == reference, (
        role,
        "Python inventory drift",
    )
    (E / (role + "-python-packages.json")).write_bytes(package_bytes)
    (E / (role + "-python-freeze.metadata-derived.txt")).write_text(
        "".join(p["name"] + "==" + p["version"] + "\n" for p in packages)
    )
    shutil.copyfile(root / "dpkg-status", E / (role + "-backend-dpkg-status.txt"))
    shutil.copyfile(
        ROOT / (role + "-frontend") / "apk-installed",
        E / (role + "-frontend-apk-installed.txt"),
    )
    shutil.copyfile(
        ROOT / (role + "-frontend") / "nginx.conf", E / (role + "-nginx.conf")
    )
    assert prepare.sha(ROOT / (role + "-frontend") / "nginx.conf") == prepare.sha(
        context / "frontend/mission-planner/nginx.conf"
    )
    modules = files(root / "diagnostic")
    assert modules == files(context / ".perf391/diagnostic")
    frozen = files(root / "acceptance")
    assert frozen == files(context / ".perf391/acceptance")
    source = {}
    for name in ["main.py", "config.yaml"]:
        assert prepare.sha(root / "app" / name) == prepare.sha(
            context / "backend/starlink-location" / name
        )
        source[name] = prepare.sha(root / "app" / name)
    for dirname in ["app", "tests"]:
        actual = files(root / "app" / dirname)
        assert actual == files(context / "backend/starlink-location" / dirname), (
            role,
            dirname,
        )
        source.update({dirname + "/" + k: v for k, v in actual.items()})
    assert prepare.sha(root / "node") == browser["node_sha256"]
    write(
        role + "-backend-modules.json",
        {"diagnostic": modules, "acceptance": frozen, "application": source},
    )
    renderer_assets = files(root / "renderer-assets")
    write(role + "-renderer-assets.json", renderer_assets)
    assets = files(E / (role + "-assets"))
    images = {}
    digests = {}
    for kind in ["backend", "frontend"]:
        image = json.loads((E / f"{role}-{kind}.image.json").read_bytes())[0]
        assert image["Os"] == "linux" and image["Architecture"] == "amd64"
        assert image["Config"]["Labels"]["diagnostic"] == "true"
        assert all(
            image["Config"]["Labels"].get(k) == v
            for k, v in plan["roles"][role]["labels"].items()
        )
        images[kind] = {
            "id": image["Id"],
            "labels": image["Config"]["Labels"],
            "repo_digests": image["RepoDigests"],
        }
        metadata = ROOT / f"{role}-{kind}.metadata.json"
        shutil.copyfile(metadata, E / metadata.name)
        m = json.loads(metadata.read_bytes())
        assert (
            m["containerimage.digest"] == image["Descriptor"]["digest"] == image["Id"]
        )
        digests[kind] = {
            "image_id": image["Id"],
            "manifest_or_index_digest": m["containerimage.digest"],
            "repo_digests": image["RepoDigests"],
            "size_bytes": image["Size"],
            "rootfs_layers": image["RootFS"]["Layers"],
        }
    deps = {
        "python_freeze_sha256": prepare.sha(
            E / (role + "-python-freeze.metadata-derived.txt")
        ),
        "npm_lock_sha256": plan["roles"][role]["package_lock_sha256"],
        "os_packages_sha256": prepare.build.digest(
            prepare.build.canonical(
                {
                    "backend": prepare.sha(E / (role + "-backend-dpkg-status.txt")),
                    "frontend": prepare.sha(E / (role + "-frontend-apk-installed.txt")),
                }
            )
        ),
        "browser_tree_sha256": browser_tree,
    }
    receipt = {
        "schema": "perf391-runtime-receipt-v1",
        "role": role,
        "plan_sha256": prepare.sha(plan_path),
        "images": images,
        "assets": assets,
        "asset_root": str(E / (role + "-assets")),
        "dependencies": deps,
        "browser": browser,
    }
    validate_receipt(receipt, plan, prepare.sha(plan_path))
    write("built-" + role + ".json", receipt)
    closure = json.loads(
        (E / (role + "-assets") / "perf391-module-closure.json").read_bytes()
    )
    live = [
        m
        for rows in closure["modules"].values()
        for m in rows
        if m["renderedLength"] > 0
        and (
            m["id"].startswith("diagnostic/")
            or any(
                m["id"].endswith(s)
                for s in [
                    "src/hooks/api/useOverviewHistory.ts",
                    "src/services/overview-history.ts",
                    "src/pages/OverviewMetricHistoryPanel.tsx",
                ]
            )
        )
    ]
    write(role + "-compiled-diagnostic-modules.json", live)
    summary["roles"][role] = {
        "receipt_validated": True,
        "receipt_sha256": prepare.sha(E / ("built-" + role + ".json")),
        "images": digests,
        "python_packages": len(packages),
        "python_package_inventory_sha256": prepare.sha(
            E / (role + "-python-packages.json")
        ),
        "diagnostic_module_count": len(modules),
        "source_file_count": len(source),
        "frozen_alias_file_count": len(frozen),
        "frontend_asset_count": len(assets),
        "frontend_asset_map_sha256": prepare.build.digest(
            prepare.build.canonical(assets)
        ),
        "compiled_closure_sha256": assets["perf391-module-closure.json"],
        "renderer_asset_count": len(renderer_assets),
        "renderer_asset_map_sha256": prepare.build.digest(
            prepare.build.canonical(renderer_assets)
        ),
    }
assert files(E / "A-assets") == files(E / "C-assets"), "A/C frontend assets differ"
assert files(ROOT / "A-backend/renderer-assets") == files(
    ROOT / "C-backend/renderer-assets"
)
summary["ac_compiled_frontend_assets_identical"] = True
summary["ac_python_inventory_matches_reference"] = True
for p in ROOT.glob("*builder.metadata.json"):
    shutil.copyfile(p, E / p.name)
write("qualification.json", summary)
print(json.dumps(summary, indent=2))
