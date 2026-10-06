"""GFS additions preserve old saved preferences and strict partial updates."""

import json

import pytest

from app.services.aviation_weather.settings import AviationSettingsStore


def test_old_settings_migrate_without_enabling_model(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"metar": True, "taf": False, "sigmet": True, "revision": 7})
    )
    settings = AviationSettingsStore(path).get()
    assert settings.metar and settings.sigmet
    assert not settings.winds and not settings.temperature
    assert settings.gfs_selection.pressure_pa == 50000
    assert settings.gfs_selection.horizon_hours == 0
    assert settings.revision == 7


def test_model_selection_is_persisted_atomically(tmp_path):
    store = AviationSettingsStore(tmp_path / "settings.json")
    value = store.update(
        {"winds": True, "gfs_selection": {"pressure_pa": 25000, "horizon_hours": 6}}
    )
    assert value.revision == 1
    assert store.get() == value
    assert store.update({"winds": True}).revision == 1
    assert store.update({"taf": True}).winds


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"winds": None},
        {"winds": 1},
        {"temperature": "true"},
        {"gfs_selection": {"pressure_pa": 80000, "horizon_hours": 0}},
        {"gfs_selection": {"pressure_pa": 50000, "horizon_hours": 1}},
        {"gfs_selection": {"pressure_pa": True, "horizon_hours": 0}},
        {"gfs_selection": {"pressure_pa": 50000, "horizon_hours": 6, "url": "evil"}},
    ],
)
def test_unsupported_selection_cannot_replace_settings(tmp_path, changes):
    store = AviationSettingsStore(tmp_path / "settings.json")
    original = store.update({"metar": True})
    with pytest.raises(ValueError):
        store.update(changes)
    assert store.get() == original
