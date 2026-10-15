"""The isolated live fixture must disconnect every external discovery path."""

import importlib
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class Disconnected(Exception):
    pass


def test_live_fixture_never_dials_hardware_or_geolocation(monkeypatch):
    class Client:
        def connect(self):
            pytest.fail("Hardware connection attempted")

        def test_connection(self):
            pytest.fail("Hardware connection test attempted")

        def get_telemetry(self):
            pytest.fail("Hardware telemetry attempted")

    class Resolver:
        def __init__(self, ip_resolver=None, geolocator=None):
            self.ip_resolver = ip_resolver
            self.geolocator = geolocator

    client_module = ModuleType("app.live.client")
    client_module.StarlinkClient = Client
    ground = ModuleType("app.services.ground_entry_point")
    ground.GroundEntryPointResolver = Resolver
    ground._resolver = Resolver()
    services = ModuleType("app.services")
    services.ground_entry_point = ground
    for name, module in {
        "app": ModuleType("app"),
        "app.live": ModuleType("app.live"),
        "app.live.client": client_module,
        "app.services": services,
        "app.services.ground_entry_point": ground,
        "grpc": SimpleNamespace(RpcError=Disconnected),
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    imported = []
    original = importlib.import_module

    def import_app(name, package=None):
        if name == "main":
            imported.append(name)
            client = Client()
            assert client.connect() is False
            assert client.test_connection() is False
            with pytest.raises(Disconnected):
                client.get_telemetry()
            assert ground._resolver.ip_resolver() is None
            assert ground._resolver.geolocator("192.0.2.1") is None
            return SimpleNamespace(app="real-app-sentinel")
        return original(name, package)

    monkeypatch.setattr(importlib, "import_module", import_app)
    fixture = (
        Path(__file__).parents[1] / "acceptance/simulation-speed/backend_fixture.py"
    )
    result = runpy.run_path(str(fixture))
    assert imported == ["main"]
    assert result["app"] == "real-app-sentinel"
