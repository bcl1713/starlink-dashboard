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


@pytest.mark.parametrize(
    "first,second", [("temperature", "winds"), ("winds", "temperature")]
)
def test_partial_enable_disables_other_layer_in_one_revision(tmp_path, first, second):
    store = AviationSettingsStore(tmp_path / "settings.json")
    before = store.update({first: True})
    after = store.update({second: True})
    assert getattr(after, second) and not getattr(after, first)
    assert after.revision == before.revision + 1
    assert store.update({second: True}).revision == after.revision
    assert store.update({"metar": True}).gfs_selection == after.gfs_selection
    off = store.update({second: False})
    assert not off.winds and not off.temperature


def test_explicit_both_true_is_rejected_without_write(tmp_path):
    store = AviationSettingsStore(tmp_path / "settings.json")
    store.update({"temperature": True})
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.update({"winds": True, "temperature": True})
    assert store.path.read_bytes() == before


def legacy_store(tmp_path, *, readonly=False):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "winds": True,
                "temperature": True,
                "metar": True,
                "taf": False,
                "sigmet": False,
                "revision": 7,
                "gfs_selection": {"pressure_pa": 25000, "horizon_hours": 6},
            }
        )
    )
    return AviationSettingsStore(path, readonly=readonly)


def test_legacy_repair_is_atomic_and_idempotent(tmp_path):
    store = legacy_store(tmp_path)
    raw = store.path.read_bytes()
    effective = store.get()
    assert effective.winds and not effective.temperature and effective.revision == 7
    assert store.path.read_bytes() == raw
    repaired, changed = store.repair_legacy()
    assert changed and repaired.revision == 8
    assert repaired.metar and repaired.gfs_selection.pressure_pa == 25000
    assert repaired.gfs_selection.horizon_hours == 6
    assert json.loads(store.path.read_bytes())["temperature"] is False
    assert store.repair_legacy() == (repaired, False)


def test_readonly_legacy_snapshot_never_writes(tmp_path):
    store = legacy_store(tmp_path, readonly=True)
    before = store.path.read_bytes()
    assert store.get().winds and not store.get().temperature
    assert store.get().revision == 7
    with pytest.raises(RuntimeError):
        store.repair_legacy()
    assert store.path.read_bytes() == before


def test_legacy_update_combines_repair_and_selection_in_one_revision(tmp_path):
    store = legacy_store(tmp_path)
    after = store.update({"temperature": True})
    assert after.temperature and not after.winds
    assert after.revision == 8 and after.metar


def test_concurrent_mode_saves_commit_exclusive_revisions(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "settings.json"

    def save(layer):
        return AviationSettingsStore(path).update({layer: True})

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(save, ["winds", "temperature"] * 12))
    assert all(result.winds != result.temperature for result in results)
    final = AviationSettingsStore(path).get()
    assert final.revision == max(result.revision for result in results)
    assert {result.revision for result in results} == set(range(1, final.revision + 1))
