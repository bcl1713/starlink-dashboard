"""Exact-source browser seam proof; always tears down its disposable stack."""

import hashlib
import importlib.util
import json
import os
import signal
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "operator_training_launcher", Path(__file__).with_name("launcher.py")
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def main():
    root = Path(sys.argv[1]).absolute()
    archive = sys.argv[2:] == ["--archive"]
    clients_only = sys.argv[2:] == ["--clients-only"]
    recovery_only = sys.argv[2:] == ["--recovery-only"]
    if sys.argv[2:] and not (archive or clients_only or recovery_only):
        raise ValueError(
            "Use --archive, --clients-only, --recovery-only, or the default guide proof"
        )
    if not str(root).startswith("/tmp/issue-376-training-proof-"):
        raise ValueError("Explicit task-owned disposable proof root required")
    training = launcher.open_owner(root)
    if not training.ownership.get("disposable"):
        raise ValueError("This proof only owns disposable training stacks")
    # Keep browser process ownership separate from checkpoint CLI command ledgers.
    runner = launcher.Owner(training.project, root / "proof-runner")
    runner.ownership.update(
        volumes=[],
        images=[],
        fixture="explicit private training browser proof",
        trainingRoot=str(root),
        candidateSha=training.ownership["candidateSha"],
    )
    runner.env.update(training.env)
    runner.env.update(
        OPERATOR_TRAINING_ORIGIN=f'http://127.0.0.1:{training.ownership["port"]}',
        OPERATOR_TRAINING_PROOF_ROOT=str(root),
        OPERATOR_TRAINING_TEST_SOURCE=str(launcher.SOURCE),
        OPERATOR_TRAINING_PYTHON=sys.executable,
        PLAYWRIGHT_BROWSERS_PATH=os.environ.get(
            "PLAYWRIGHT_BROWSERS_PATH", "/home/oracle-worker/.cache/ms-playwright"
        ),
        npm_config_offline="true",
        npm_config_update_notifier="false",
    )
    runner.persist()
    handlers = {
        number: signal.signal(number, runner.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    report = {
        "candidateSha": training.ownership["candidateSha"],
        "checksPassed": False,
        "scope": (
            "recovery-only"
            if recovery_only
            else (
                "clients-only"
                if clients_only
                else "course-archive" if archive else "guide-clients"
            )
        ),
    }
    try:
        current = runner.execute(
            ["git", "rev-parse", "HEAD"], cwd=launcher.SOURCE
        ).strip()
        if current != training.ownership["candidateSha"]:
            raise ValueError(
                "Proof requires training images and browser tests from the same committed SHA"
            )
        images = {}
        for service in ("backend", "frontend"):
            tag = f"{training.project}-{service}:{current}"
            image_format = '{"id":{{json .Id}},"revision":{{json (index .Config.Labels "org.opencontainers.image.revision")}}}'
            inspected = json.loads(
                runner.execute(
                    ["docker", "image", "inspect", "--format", image_format, tag]
                )
            )
            revision = inspected["revision"]
            if revision != current:
                raise ValueError(
                    "Training image revision does not match the committed candidate"
                )
            images[service] = {"tag": tag, "id": inspected["id"], "revision": revision}
        (root / "image-identity.json").write_text(
            json.dumps(
                {
                    "candidateSha": current,
                    "sourceArchiveSha256": hashlib.sha256(
                        (root / "source.tar").read_bytes()
                    ).hexdigest(),
                    "images": images,
                    "capturedAfterOwnedTeardown": False,
                },
                indent=2,
            )
        )
        if not (clients_only or recovery_only):
            runner.execute(
                [
                    "timeout",
                    "--kill-after=10s",
                    "10m",
                    "npx",
                    "--no-install",
                    "playwright",
                    "test",
                    "--config",
                    "playwright.operator-training.config.ts",
                ],
                cwd=launcher.SOURCE / "frontend/mission-planner",
                timeout=620,
            )
        targeted = (
            "OPERATOR_TRAINING_RECOVERY_ONLY"
            if recovery_only
            else "OPERATOR_TRAINING_CLIENTS_ONLY"
        )
        runner.env[targeted] = "true"
        runner.execute(
            [
                "timeout",
                "--kill-after=10s",
                "6m",
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "playwright.operator-training.config.ts",
            ],
            cwd=launcher.SOURCE / "frontend/mission-planner",
            timeout=380,
        )
        runner.env.pop(targeted)
        if archive:
            runner.env["OPERATOR_TRAINING_RECORDS_ONLY"] = "true"
            runner.execute(
                [
                    "timeout",
                    "--kill-after=10s",
                    "5m",
                    "npx",
                    "--no-install",
                    "playwright",
                    "test",
                    "--config",
                    "playwright.operator-training.config.ts",
                ],
                cwd=launcher.SOURCE / "frontend/mission-planner",
                timeout=320,
            )
            runner.env.pop("OPERATOR_TRAINING_RECORDS_ONLY")
            runner.env["OPERATOR_TRAINING_DECISIONS_ONLY"] = "true"
            runner.execute(
                [
                    "timeout",
                    "--kill-after=10s",
                    "6m",
                    "npx",
                    "--no-install",
                    "playwright",
                    "test",
                    "--config",
                    "playwright.operator-training.config.ts",
                ],
                cwd=launcher.SOURCE / "frontend/mission-planner",
                timeout=380,
            )
            runner.env.pop("OPERATOR_TRAINING_DECISIONS_ONLY")
            destination = launcher.open_owner(
                root / "import-destination",
                create=True,
                disposable=True,
                destination=True,
                port=56534,
            )
            for number in handlers:
                signal.signal(number, destination.signal)
            try:
                launcher.start(destination, relay=True)
            finally:
                destination.stop_child()
                for number in handlers:
                    signal.signal(number, runner.signal)
            if destination.ownership["candidateSha"] != current:
                raise ValueError("Archive destination must use the same candidate")
            destination_images = {}
            for service in ("backend", "frontend"):
                tag = f"{destination.project}-{service}:{current}"
                inspected = json.loads(
                    destination.execute(
                        ["docker", "image", "inspect", "--format", image_format, tag]
                    )
                )
                if inspected["revision"] != current:
                    raise ValueError("Archive destination image revision differs")
                destination_images[service] = {"tag": tag, **inspected}
            (root / "destination-image-identity.json").write_text(
                json.dumps(
                    {
                        "candidateSha": current,
                        "sourceArchiveSha256": hashlib.sha256(
                            (destination.root / "source.tar").read_bytes()
                        ).hexdigest(),
                        "images": destination_images,
                        "capturedBeforeArchiveBrowser": True,
                    },
                    indent=2,
                )
            )
            runner.env.update(
                OPERATOR_TRAINING_ARCHIVE_ONLY="true",
                OPERATOR_TRAINING_ARCHIVE_ORIGIN="http://127.0.0.1:56534",
            )
            runner.execute(
                [
                    "timeout",
                    "--kill-after=10s",
                    "15m",
                    "npx",
                    "--no-install",
                    "playwright",
                    "test",
                    "--config",
                    "playwright.operator-training.config.ts",
                ],
                cwd=launcher.SOURCE / "frontend/mission-planner",
                timeout=920,
            )
            runner.execute(
                [
                    sys.executable,
                    str(Path(__file__).with_name("inspect_archive.py")),
                    str(root),
                ],
                timeout=120,
            )
            report["archiveInspection"] = json.loads(
                (root / "archive-inspection.json").read_text()
            )
        report["checksPassed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        runner.stop_child()
        try:
            report["cleanup"] = launcher.stop(launcher.open_owner(root))
            child_state = root / "import-destination/ownership.json"
            if child_state.exists():
                report["destinationCleanup"] = json.loads(child_state.read_text())[
                    "remaining"
                ]
        finally:
            (root / "proof-summary.json").write_text(json.dumps(report, indent=2))
            for number, handler in handlers.items():
                signal.signal(number, handler)
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
