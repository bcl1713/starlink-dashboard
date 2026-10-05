"""Live rejection lane only: real app with disconnected dish connection."""

import importlib

from app.live.client import StarlinkClient

StarlinkClient.connect = lambda self: False
StarlinkClient.test_connection = lambda self: False

app = importlib.import_module("main").app

__all__ = ["app"]
