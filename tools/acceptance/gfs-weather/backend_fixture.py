"""Existing radar/bulletin fixture, plus an explicit historical replay clock."""

import importlib.util
import json
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "aviation_acceptance", "/aviation-acceptance/backend_fixture.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from app.services.aviation_weather.gfs.bridge import GfsBridge

original_clock = module.module.fixture_utc_ms


def shared_utc_ms():
    values = json.loads(Path("/control/control.json").read_bytes())
    if "replay_monotonic" in values:
        return int(
            values["replay_utc_ms"]
            + (time.monotonic() - values["replay_monotonic"]) * 1000
        )
    return original_clock()


module.module.fixture_utc_ms = shared_utc_ms


class ReplayBridge(GfsBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, **kwargs, clock=lambda: module.module.fixture_utc_ms() / 1000
        )


module.main.GfsBridge = ReplayBridge
app = module.app
