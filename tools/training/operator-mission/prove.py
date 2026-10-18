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
    report = {"candidateSha": training.ownership["candidateSha"], "checksPassed": False}
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
            inspected = json.loads(runner.execute(["docker", "image", "inspect", tag]))[
                0
            ]
            revision = inspected["Config"]["Labels"].get(
                "org.opencontainers.image.revision"
            )
            if revision != current:
                raise ValueError(
                    "Training image revision does not match the committed candidate"
                )
            images[service] = {"tag": tag, "id": inspected["Id"], "revision": revision}
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
        report["checksPassed"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        runner.stop_child()
        try:
            report["cleanup"] = launcher.stop(launcher.open_owner(root))
        finally:
            (root / "proof-summary.json").write_text(json.dumps(report, indent=2))
            for number, handler in handlers.items():
                signal.signal(number, handler)
            print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
