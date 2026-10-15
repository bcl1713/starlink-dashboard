"""Live rejection lane only: real app with disconnected external discovery."""

import importlib
from grpc import RpcError

from app.live.client import StarlinkClient
from app.services import ground_entry_point


def disconnected_telemetry(self):
    raise RpcError("Hardware disconnected in controlled acceptance")


StarlinkClient.connect = lambda self: False
StarlinkClient.test_connection = lambda self: False
StarlinkClient.get_telemetry = disconnected_telemetry
ground_entry_point._resolver = ground_entry_point.GroundEntryPointResolver(
    ip_resolver=lambda: None, geolocator=lambda ip: None
)

app = importlib.import_module("main").app

__all__ = ["app"]
