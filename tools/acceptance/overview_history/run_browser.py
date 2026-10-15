"""Reuse the validated native browser authority for task-owned measurements."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.acceptance.platform.health import (
    PlatformHealthExecutor,
    start_final_browser_session,
)
from tools.acceptance.platform.runner import _load_profile, _probe


def execute(
    arguments, *, profile, start=start_final_browser_session, launch=subprocess.Popen
):
    output = Path(arguments[arguments.index("--artifacts") + 1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    platform = output / "platform"
    session = start(profile, platform, PlatformHealthExecutor(probe=_probe))
    child = None
    cleanup = {"status": "pending"}
    try:
        (output / "platform.json").write_text(
            json.dumps({"metrics": session.metrics, "webgl2": session.webgl2}, indent=2)
        )
        extra = []
        if os.environ.get("OVERVIEW_PROFILE_CONTROLS") == "1":
            extra += ["--controls", "--record-video"]
        command = [
            "node",
            str(ROOT / "tools/acceptance/journeys/overview-history-performance.mjs"),
            "--session",
            session.cdp_url,
            *arguments,
            *extra,
        ]
        child = launch(
            command,
            env={**os.environ, "OVERVIEW_PROFILE_RENDERER": session.webgl2["renderer"]},
            start_new_session=True,
        )
        return child.wait()
    finally:
        try:
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
            session.close()
            cleanup["status"] = "passed"
        except BaseException as error:
            cleanup = {"status": "failed", "error": str(error)}
            raise
        finally:
            platform.mkdir(parents=True, exist_ok=True)
            for name, content in session.artifacts.items():
                (platform / name).write_bytes(content)
            (output / "browser-cleanup.json").write_text(json.dumps(cleanup, indent=2))


def main():
    descriptor = os.environ.get("OVERVIEW_PROFILE_BROWSER_PROFILE")
    if not descriptor:
        raise ValueError(
            "OVERVIEW_PROFILE_BROWSER_PROFILE must name a provisioned platform descriptor"
        )

    def interrupted(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    return execute(sys.argv[1:], profile=_load_profile(Path(descriptor)))


if __name__ == "__main__":
    sys.exit(main())
