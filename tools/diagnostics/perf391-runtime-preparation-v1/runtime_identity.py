"""Receipt-bound diagnostic lane; historical benchmark identity is separate."""

import json
import subprocess
from pathlib import Path

from prepare import HERE, OVERLAY_FILES, build, sha

DIAGNOSTIC_NODE_VERSION = "22.22.2"
DIAGNOSTIC_NODE_SHA256 = (
    "81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90"
)
HISTORICAL_NODE_VERSION = "22.12.0"
HISTORICAL_NODE_SHA256 = (
    "177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9"
)


def validate_diagnostic_node(browser):
    build.require(
        (browser["node_version"], browser["node_sha256"])
        == (DIAGNOSTIC_NODE_VERSION, DIAGNOSTIC_NODE_SHA256),
        "receipt-bound diagnostic Node identity (historical benchmark Node is separate)",
    )


def verify_runtime_overlay(plan):
    """Authorize only the explicitly inventoried correction over the frozen plan.

    Neither the original build-plan bytes nor their receipt binding is rewritten.
    """
    correction = json.loads((HERE / "node-contract-overlay.json").read_bytes())
    build.require(
        plan["overlay_files"] == correction["original_overlay_files"],
        "original runtime overlay identity",
    )
    build.require(
        build.digest(build.canonical(plan["overlay_files"])) == plan["overlay_sha256"],
        "original runtime overlay digest",
    )
    expected = correction["corrected_overlay_files"]
    build.require(
        set(expected) == {*OVERLAY_FILES, "runtime_identity.py"},
        "corrected runtime overlay inventory",
    )
    build.require(
        all(sha(HERE / name) == digest for name, digest in expected.items()),
        "corrected runtime overlay drift",
    )


def verify_runtime_identity(node, receipt):
    """Hash first; run only Node --version and package import, never Chromium."""
    browser = receipt["browser"]
    validate_diagnostic_node(browser)
    build.require(
        sha(node) == browser["node_sha256"],
        "actual diagnostic Node executable hash differs",
    )
    version = (
        subprocess.check_output([str(node), "--version"], text=True, timeout=3)
        .strip()
        .removeprefix("v")
    )
    build.require(
        version == browser["node_version"], "actual diagnostic Node version differs"
    )
    root = Path(browser["playwright_root"]) / "node_modules"
    packages = {}
    for name in ("playwright", "playwright-core"):
        path = root / name / "package.json"
        package = json.loads(path.read_bytes())
        build.require(
            package["version"] == "1.63.0" and package["engines"]["node"] == ">=20",
            "Playwright package version/Node engine compatibility",
        )
        packages[name] = {
            "version": package["version"],
            "node_engine": package["engines"]["node"],
            "sha256": sha(path),
        }
    browsers = root / "playwright-core/browsers.json"
    chromium = next(
        b
        for b in json.loads(browsers.read_bytes())["browsers"]
        if b["name"] == "chromium"
    )
    build.require(chromium["revision"] == "1243", "Chromium revision identity")
    executable = Path(browser["chromium_executable"])
    build.require(
        "chromium-1243" in executable.parts
        and sha(executable) == browser["chromium_sha256"],
        "Chromium executable identity",
    )
    # Import the installed API and resolve its configured executable without launching.
    script = "const p=require(process.argv[1]); console.log(JSON.stringify({executable:p.chromium.executablePath(),launch:typeof p.chromium.launch}));"
    imported = json.loads(
        subprocess.check_output(
            [str(node), "-e", script, str(root / "playwright")], text=True, timeout=5
        )
    )
    build.require(
        Path(imported["executable"]).resolve() == executable.resolve()
        and imported["launch"] == "function",
        "Playwright configured Chromium identity",
    )
    return {
        "lane": "diagnostic-functionality-only",
        "node_version": version,
        "node_sha256": sha(node),
        "packages": packages,
        "chromium_revision": "1243",
        "chromium_sha256": sha(executable),
        "browsers_json_sha256": sha(browsers),
        "api_imported_without_launch": True,
        "browser_launched": False,
        "runtime_compatibility_qualified": False,
        "historical_node_version": HISTORICAL_NODE_VERSION,
        "historical_node_sha256": HISTORICAL_NODE_SHA256,
    }
