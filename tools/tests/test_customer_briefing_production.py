"""Production acceptance must own and reap every command, including failed runs."""

import importlib.util
import json
import os
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/acceptance/customer-briefing/production.py"


def module():
    assert ENTRY.exists(), "production acceptance ownership is missing"
    spec = importlib.util.spec_from_file_location("briefing_production", ENTRY)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_command_ownership_and_output_are_retained_before_cleanup(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    assert json.loads((tmp_path / "ownership.json").read_text())["commands"] == []
    assert (
        owner.execute([sys.executable, "-c", "print('real process')"])
        == "real process\n"
    )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["pid"] > 0 and entry["pgid"] == entry["pid"]
    assert entry["returncode"] == 0 and entry["reaped"]
    with pytest.raises(ProcessLookupError):
        os.kill(entry["pid"], 0)


def test_timeout_reaps_the_owned_process_group(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    with pytest.raises(TimeoutError):
        owner.execute(
            [sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1
        )
    entry = json.loads((tmp_path / "ownership.json").read_text())["commands"][0]
    assert entry["reaped"] and entry["returncode"] < 0
    with pytest.raises(ProcessLookupError):
        os.killpg(entry["pgid"], 0)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signal_marks_cancellation_and_prevents_next_launch(tmp_path, signum):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    with pytest.raises(InterruptedError):
        owner.signal(signum, None)
    with pytest.raises(InterruptedError):
        owner.execute([sys.executable, "-c", "raise Exception('must not run')"])
    assert json.loads((tmp_path / "ownership.json").read_text())["cancelled"]


def test_failed_build_still_removes_owned_runtime_and_temporary_paths(tmp_path):
    value = module()
    owner = value.ProductionOwner("briefing-private-test", tmp_path)
    context = tmp_path / "owned-context"
    context.mkdir()
    owner.ownership["temporaryPaths"].append(str(context))
    with pytest.raises(RuntimeError):
        owner.execute([sys.executable, "-c", "raise SystemExit(2)"])
    # Docker is the external boundary; exercise real ownership/teardown decisions.
    calls = []
    owner.execute = lambda command, **kwargs: calls.append(command) or ""
    cleanup = owner.close()
    assert cleanup["childrenReaped"] and cleanup["composeRemoved"]
    assert not context.exists()
    assert any("down" in command and "--volumes" in command for command in calls)


def test_surviving_resource_blocks_cleanup_success_and_preserves_context(tmp_path):
    owner = module().ProductionOwner("briefing-private-test", tmp_path)
    context = tmp_path / "owned-context"
    context.mkdir()
    owner.ownership["temporaryPaths"].append(str(context))
    owner.execute = lambda command, **kwargs: (
        "owned-container\n" if "ps" in command else ""
    )
    with pytest.raises(RuntimeError, match="remain"):
        owner.close()
    assert context.exists()
    assert not json.loads((tmp_path / "ownership.json").read_text())["cleanup"][
        "composeRemoved"
    ]
