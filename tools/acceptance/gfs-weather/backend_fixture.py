"""Existing radar/bulletin fixture, plus an explicit historical replay clock."""

import importlib.util

spec = importlib.util.spec_from_file_location(
    "aviation_acceptance", "/aviation-acceptance/backend_fixture.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from app.services.aviation_weather.gfs.bridge import GfsBridge


class ReplayBridge(GfsBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, **kwargs, clock=lambda: module.module.fixture_utc_ms() / 1000
        )


module.main.GfsBridge = ReplayBridge
app = module.app
