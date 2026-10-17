"""Optional runtime must preserve the baseline and never open another mode."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.operator import router
from app.operator.runtime import OperatorRuntime
from app.operator.settings import OperatorSettings


def client_for(runtime):
    app = FastAPI()
    app.state.operator_runtime = runtime
    app.include_router(router)

    @app.get("/baseline")
    def baseline():
        return {"ready": True}

    return TestClient(app)


def test_disabled_and_unhealthy_isolation(tmp_path, clock):
    root = tmp_path / "absent"
    settings = OperatorSettings(enabled=False, root=root, source_mode="simulation")
    runtime = OperatorRuntime.start(settings, clock=clock)
    with client_for(runtime) as client:
        assert client.get("/api/v2/operator/health").status_code == 404
        assert client.post("/api/v2/operator/records", json={}).status_code == 404
        assert client.get("/baseline").json() == {"ready": True}
    assert not root.exists()
    runtime.close()
    runtime = OperatorRuntime.start(
        OperatorSettings(enabled=True, root=root), clock=clock
    )
    with client_for(runtime) as client:
        result = client.get("/api/v2/operator/health")
        assert result.status_code == 503
        assert result.json()["enabled"] is True
        assert result.json()["ready"] is False
        assert client.get("/baseline").status_code == 200
    assert not root.exists()
    runtime.close()


def test_health_close_and_mode_switch(service, clock):
    settings = service.store.settings
    runtime = OperatorRuntime.start(settings, clock=clock)
    assert runtime.health().ready
    assert runtime.health().api_epoch == service.store.health().api_epoch
    assert runtime.health().store_id == service.store.health().store_id
    runtime.close()
    assert not runtime.health().ready
    simulation = OperatorRuntime.start(
        replace(settings, source_mode="simulation", simulation_run_id="actual-run"),
        clock=clock,
    )
    assert simulation.service is None
    assert not simulation.health().ready
    assert not (settings.root / "simulation").exists()
    simulation.close()


def test_binding_uses_actual_run_then_explicit_demo_and_missing_is_unavailable(
    tmp_path, clock, monkeypatch
):
    from app.operator.runtime import OperatorRuntimeBinding, enabled
    from app.operator.store import OperatorStore

    root = tmp_path / "operator"
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(root))
    monkeypatch.setenv("OPERATOR_SIMULATION_RUN_ID", "demo")
    monkeypatch.setenv("OPERATOR_SOURCE_MODE", "live")
    for run in ("actual", "demo"):
        store = OperatorStore.open(
            OperatorSettings(
                enabled=True, root=root, source_mode="simulation", simulation_run_id=run
            ),
            initialize=True,
            clock=clock,
        )
        store.close()
    context = ["simulation", "actual"]
    binding = OperatorRuntimeBinding(clock=clock, context=lambda: tuple(context))
    with binding.access() as actual:
        assert actual.health().simulation_run_id == "actual"
        assert actual.health().ready
        actual_epoch = actual.health().api_epoch
    context[1] = None
    with binding.access() as demo:
        assert demo.health().simulation_run_id == "demo"
        assert demo.health().api_epoch != actual_epoch
    assert not actual.health().ready
    monkeypatch.delenv("OPERATOR_SIMULATION_RUN_ID")
    with binding.access() as missing:
        assert enabled(missing)
        assert missing.service is None
        assert missing.health().simulation_run_id is None
    binding.close()


def test_binding_serializes_rebind_and_old_epoch_cannot_write_new_namespace(
    tmp_path, clock, record_data, monkeypatch
):
    from uuid import uuid4

    from app.operator.errors import OperatorError
    from app.operator.models import CreateRecord
    from app.operator.runtime import OperatorRuntimeBinding
    from app.operator.store import OperatorStore

    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(tmp_path))
    for run in ("first", "second"):
        OperatorStore.open(
            OperatorSettings(
                enabled=True,
                root=tmp_path,
                source_mode="simulation",
                simulation_run_id=run,
            ),
            initialize=True,
            clock=clock,
        ).close()
    context = ["simulation", "first"]
    binding = OperatorRuntimeBinding(clock=clock, context=lambda: tuple(context))
    entered, release = Event(), Event()

    def hold_request():
        with binding.access() as runtime:
            entered.set()
            assert release.wait(5)
            assert runtime.health().ready
            return runtime.health().api_epoch

    def next_request():
        with binding.access() as runtime:
            return runtime

    with ThreadPoolExecutor(max_workers=2) as pool:
        held = pool.submit(hold_request)
        assert entered.wait(5)
        context[1] = "second"
        rebound = pool.submit(next_request)
        release.set()
        epoch = held.result(timeout=5)
        runtime = rebound.result(timeout=5)
    assert runtime.health().simulation_run_id == "second"
    with pytest.raises(OperatorError) as error:
        runtime.service.execute(
            CreateRecord(**record_data), key=str(uuid4()), epoch=str(epoch)
        )
    assert error.value.code == "store_epoch_changed"
    binding.close()


@pytest.mark.parametrize("damaged", [False, True])
def test_unavailable_operator_preserves_main_status_config_and_missions(
    service, monkeypatch, damaged
):
    import main
    from app.models.config import SimulationConfig

    config = SimulationConfig(mode="live")

    class LocalLiveCoordinator(main.SimulationCoordinator):
        def __init__(self, config):
            super().__init__(config)
            self.client = None

    settings = service.store.settings
    service.store.close()
    if damaged:
        settings.database_path.write_bytes(b"corrupt synthetic database")
    else:
        settings.database_path.unlink()
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(settings.root))
    monkeypatch.setattr(main.ConfigManager, "load", lambda self: config)
    monkeypatch.setattr(main, "LiveCoordinator", LocalLiveCoordinator)
    monkeypatch.setattr(main, "refresh_ground_entry_point_metrics", lambda: None)
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    with TestClient(main.app) as client:
        result = client.get("/api/v2/operator/health")
        assert result.status_code == 503
        assert result.json()["enabled"] is True
        assert not result.json()["ready"]
        assert str(settings.root) not in result.text
        for path in ("/health", "/api/status", "/api/config", "/api/v2/missions"):
            assert client.get(path).status_code == 200
    assert not hasattr(main.app.state, "operator_binding")
