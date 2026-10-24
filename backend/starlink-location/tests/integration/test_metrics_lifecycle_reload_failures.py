"""Transient source read failures recover without files changing again."""

import json

import pytest

import main
from app.core.metrics import prometheus_metrics as metrics
from app.models.poi import POICreate
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("failure", ["lock", "format"])
async def test_transient_poi_reload_failure_recovers_on_existing_refresh(
    background_runtime, monkeypatch, failure
):
    import app.services.poi.manager as poi_module

    owner = main.app.state.metrics_refresh_owner
    owner._background_enabled = True
    manager = main.app.state.poi_manager
    manager.create_poi(POICreate(name="Before failure", latitude=1, longitude=1))
    await owner.refresh_without_collection()
    data = json.loads(manager.pois_file.read_text())
    next(iter(data["pois"].values()))["name"] = "Recovered"
    manager.pois_file.write_text(json.dumps(data))
    lock = poi_module.FileLock

    class BusyLock:
        def __init__(self, *args, **kwargs):
            pass

        def acquire(self, *args, **kwargs):
            raise TimeoutError("injected transient POI read lock")

    if failure == "lock":
        monkeypatch.setattr(poi_module, "FileLock", BusyLock)
        manager.reload_pois()
    else:
        manager.pois_file.write_text("[]")
        with pytest.raises(AttributeError):
            manager.reload_pois()
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "failed"
    monkeypatch.setattr(poi_module, "FileLock", lock)
    if failure == "format":
        manager.pois_file.write_text(json.dumps(data))
    # The same refresh runs on retained-source deadlines. No file edit,
    # observation or retry timer is required to recover.
    main._refresh_metrics_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    names = {
        sample.labels.get("name")
        for family in metrics.REGISTRY.collect()
        if family.name == "starlink_eta_poi_seconds"
        for sample in family.samples
    }
    assert names == {"Recovered"}
