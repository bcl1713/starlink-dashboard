"""Production Nginx source APIs, installed browser and delivered export qualification."""

import json
import os
from pathlib import Path

from production import ROOT, free_loopback_port
from production_controls import ProductionApi, download_prepared, inspect_download
from production_seed import provider_seed
from seed import seed


def qualify(owner):
    source = Path(owner.env["BRIEFING_SOURCE_ROOT"])
    tools = source / "tools/acceptance/pop-transitions"
    owner.compose(
        "run",
        "--rm",
        "--no-deps",
        "starlink-location",
        "python",
        "-c",
        provider_seed(),
        timeout=30,
    )
    owner.compose("up", "-d", "--wait", "--wait-timeout", "150", timeout=180)
    api = ProductionApi(owner)
    fixtures = seed(api, owner.root)
    provider = json.loads(
        owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            (tools / "advisory_probe.py").read_text(),
            timeout=30,
        ).splitlines()[-1]
    )
    (owner.root / "provider-fixtures.json").write_text(json.dumps(provider, indent=2))
    browser_env = dict(owner.env)
    browser_env.update(
        POP_EVIDENCE_ROOT=str(owner.root),
        POP_ORIGIN=api.origin,
        POP_CDP_PORT=str(free_loopback_port()),
    )
    owner.ownership["browserCdpListener"] = {
        "address": "127.0.0.1",
        "port": int(browser_env["POP_CDP_PORT"]),
    }
    owner.persist()
    browser_root = Path(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright")
    )
    owner.execute(
        [
            "node",
            str(
                source
                / "tools/acceptance/browser/provision-v2-mission-retirement-chromium.mjs"
            ),
            "--mode",
            "verify",
            "--project-dir",
            str(ROOT / "frontend/mission-planner"),
            "--browser-root",
            str(browser_root),
            "--task-root",
            str(owner.root),
            "--provenance-file",
            str(owner.root / "browser-provenance.json"),
        ],
        timeout=30,
    )
    owner.execute(
        [
            "npm",
            "--prefix",
            "frontend/mission-planner",
            "exec",
            "--",
            "playwright",
            "test",
            "--config",
            "frontend/mission-planner/playwright.pop-transitions.config.ts",
        ],
        timeout=240,
        env=browser_env,
    )
    reports = {}
    for name in ("crossing", "no-crossing", "dateline", "overlap", "continuation"):
        destination = owner.root / "downloads" / name
        destination.mkdir(parents=True)
        content, headers, seconds, stages = download_prepared(
            api, fixtures[name]["missionId"], timeout=600
        )
        (destination / "download.zip").write_bytes(content)
        (destination / "preparation-stages.json").write_text(
            json.dumps(stages, indent=2)
        )
        report = inspect_download(content, headers, "included")
        (destination / "download-inspection.json").write_text(
            json.dumps(report, indent=2)
        )
        result = owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "root",
            "--entrypoint",
            "python",
            "-e",
            "PYTHONPATH=/acceptance:/app:/home/appuser/.local/lib/python3.11/site-packages",
            "-v",
            f"{destination}:/probe-evidence",
            "-v",
            f"{tools}:/pop-acceptance:ro",
            "starlink-location",
            "/pop-acceptance/pdf_probe.py",
            "/probe-evidence/download.zip",
            "/probe-evidence/actual-pdf",
            timeout=240,
        )
        proof = json.loads(result.splitlines()[-1])
        if name == "continuation":
            assert proof["pageCount"] > 1, "Continuation control did not continue"
        reports[name] = {"seconds": seconds, "pdf": proof}
    return {
        "browser": "CDP 1920x1080 real production API",
        "pdfs": reports,
        "providerFixtures": provider,
    }
