"""Replay UTC remains identical in independent API and worker processes."""

import importlib.util
from pathlib import Path


def test_source_replay_clock_uses_shared_anchor_instead_of_process_start(monkeypatch):
    path = (
        Path(__file__).resolve().parents[4]
        / "tools/acceptance/gfs-weather/source_fixture.py"
    )
    spec = importlib.util.spec_from_file_location("source_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "control",
        lambda: {
            "replay_utc_ms": 1791288447620,
            "replay_monotonic": 10.0,
        },
    )
    monkeypatch.setattr(module.time, "monotonic", lambda: 20.0)
    assert module.clock() == 1791288457.620
    module._anchor = None  # A second process starts later.
    monkeypatch.setattr(module.time, "monotonic", lambda: 30.0)
    assert module.clock() == 1791288467.620
