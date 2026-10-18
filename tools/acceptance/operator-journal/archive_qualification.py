"""Production single-package acceptance, restart controls and rendered workflows."""

import base64
import json
import os


def qualify_archive(owner):
    from run import ROOT, run_checks

    def backend():
        output = owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "/acceptance/archive_probe.py",
            timeout=1200,
        )
        result = json.loads(output.splitlines()[-1])
        (owner.root / "archive-roundtrip.json").write_text(json.dumps(result, indent=2))
        for source, target in (
            ("synthetic-complete-mission.zip", "synthetic-complete-mission.zip"),
            ("synthetic-customer-brief.pdf", "synthetic-customer-brief.pdf"),
        ):
            # docker cp cannot remount the read-only fixture mount on the
            # managed rootless daemon. Transfer only these synthetic bytes via
            # exec stdout, with the same bounded, recorded owner command.
            encoded = owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "-c",
                "import base64; from pathlib import Path; print(base64.b64encode(Path("
                + repr("/app/data/operator/archive-acceptance/" + source)
                + ").read_bytes()).decode())",
                timeout=30,
            )
            (owner.root / target).write_bytes(
                base64.b64decode(encoded.strip(), validate=True)
            )
        return result

    def export_failure():
        database = "/app/data/operator/simulation/synthetic-operator-demo-v1/operations.sqlite3"

        def media(mode, directory_mode):
            script = f"from pathlib import Path; p=Path({database!r}); p.parent.chmod({directory_mode}); [(f.chmod({mode})) for f in p.parent.glob('operations.sqlite3*')]"
            owner.compose(
                "exec",
                "-T",
                "--user",
                "0",
                "starlink-location",
                "python",
                "-c",
                script,
                timeout=30,
            )

        try:
            media("0o400", "0o500")
            script = """import httpx,json
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as client:
 responses=[client.post('/api/v2/missions/synthetic-mission-a/export-preparations'), client.post('/api/v2/missions/synthetic-mission-a/export')]
 assert all(r.status_code==503 for r in responses), [(r.status_code,r.text) for r in responses]
 assert all('application/zip' not in r.headers.get('content-type','') for r in responses)
 print(json.dumps({'enabledUnreadableJournalReturns503':True,'noFalseArchiveDownload':True}))
"""
            output = owner.compose(
                "exec",
                "-T",
                "--user",
                "appuser",
                "starlink-location",
                "python",
                "-c",
                script,
                timeout=60,
            )
            result = json.loads(output.splitlines()[-1])
            (owner.root / "archive-failure.json").write_text(
                json.dumps(result, indent=2)
            )
            return result
        finally:
            media("0o600", "0o700")

    def restart():
        script = """import hashlib,json
from pathlib import Path
import httpx
root=Path('/app/data/operator/archive-acceptance')
job=json.loads((root/'synthetic-ready-job.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=30) as client:
 response=client.get(job['download_url']); response.raise_for_status()
 assert response.content==(root/'synthetic-latest-mission.zip').read_bytes()
 print(json.dumps({'readyDownloadAfterRestartIdentical':True,'sha256':hashlib.sha256(response.content).hexdigest()}))
"""
        owner.compose("restart", "starlink-location", timeout=90)
        owner.compose(
            "up", "-d", "--no-build", "--wait", "--wait-timeout", "180", timeout=210
        )
        output = owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            script,
            timeout=90,
        )
        result = json.loads(output.splitlines()[-1])
        (owner.root / "archive-restart.json").write_text(json.dumps(result, indent=2))
        return result

    def browser():
        env = owner.env | {
            "OPERATOR_ACCEPTANCE_ORIGIN": f"http://127.0.0.1:{owner.ownership['port']}",
            "OPERATOR_ACCEPTANCE_PROJECT": owner.project,
            "OPERATOR_ACCEPTANCE_EVIDENCE": str(owner.root),
            "OPERATOR_ARCHIVE_ACCEPTANCE": "true",
            "PLAYWRIGHT_BROWSERS_PATH": os.environ.get(
                "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
            ),
            "npm_config_offline": "true",
            "npm_config_update_notifier": "false",
        }
        owner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "15m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-journal.config.ts",
                "--grep",
                "single mission ZIP archive",
            ],
            timeout=920,
            cwd=ROOT / "frontend/mission-planner",
            env=env,
        )
        return json.loads((owner.root / "archive-browser.json").read_text())

    return run_checks(
        owner.root,
        {
            "singlePackageRoundTrip": backend,
            "exportFailure": export_failure,
            "restartFrozenDownload": restart,
            "productionBrowser": browser,
        },
    )
