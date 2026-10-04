"""The browser bridge cleans only the session and child it started."""

import json
from types import SimpleNamespace

import pytest

from tools.acceptance.overview_history.run_browser import execute


@pytest.mark.parametrize("returncode", [0, 7])
def test_bridge_retains_platform_artifacts_and_closes_on_child_exit(
    tmp_path, returncode
):
    calls = []
    session = SimpleNamespace(
        cdp_url="http://127.0.0.1:9222",
        webgl2={"renderer": "SwiftShader"},
        metrics={"width": 1920},
        artifacts={"card.txt": b"neutral"},
        close=lambda: calls.append("closed"),
    )
    child = SimpleNamespace(wait=lambda: returncode, poll=lambda: returncode)

    def launch(command, **kwargs):
        assert command[0] == "node"
        assert command[command.index("--session") + 1] == session.cdp_url
        assert kwargs["start_new_session"] is True
        assert kwargs["env"]["OVERVIEW_PROFILE_RENDERER"] == "SwiftShader"
        return child

    result = execute(
        ["--artifacts", str(tmp_path), "--origin", "http://127.0.0.1:15224"],
        profile=object(),
        start=lambda *args, **kwargs: session,
        launch=launch,
    )
    assert result == returncode
    assert calls == ["closed"]
    assert (tmp_path / "platform/card.txt").read_bytes() == b"neutral"
    assert (
        json.loads((tmp_path / "browser-cleanup.json").read_text())["status"]
        == "passed"
    )


def test_bridge_closes_session_when_launch_fails(tmp_path):
    calls = []
    session = SimpleNamespace(
        cdp_url="http://127.0.0.1:9222",
        webgl2={"renderer": "SwiftShader"},
        metrics={},
        artifacts={},
        close=lambda: calls.append("closed"),
    )

    def fail(*args, **kwargs):
        raise OSError("launch failed")

    with pytest.raises(OSError, match="launch failed"):
        execute(
            ["--artifacts", str(tmp_path)],
            profile=object(),
            start=lambda *args, **kwargs: session,
            launch=fail,
        )
    assert calls == ["closed"]
