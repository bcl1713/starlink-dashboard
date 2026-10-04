import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.overview_adsb_settings import AdsbSettingsStore


def test_default_settings_are_off_with_revision_zero(tmp_path):
    assert AdsbSettingsStore(tmp_path / "adsb.json").get().model_dump() == {
        "enabled": False,
        "mode": "military_and_included",
        "include_hexes": [],
        "exclude_hexes": [],
        "callsign_substrings": [],
        "revision": 0,
    }


def test_partial_updates_preserve_lists_and_increment_revision(tmp_path):
    store = AdsbSettingsStore(tmp_path / "adsb.json")
    assert store.update({"include_hexes": [" 00ab12 ", "00AB12"]}).include_hexes == [
        "00AB12"
    ]
    changed = store.update({"mode": "included_only"})
    assert changed.include_hexes == ["00AB12"]
    assert changed.revision == 2


def test_callsigns_trim_deduplicate_ignore_blanks(tmp_path):
    assert AdsbSettingsStore(tmp_path / "a.json").update(
        {
            "callsign_substrings": [" rch ", "", "RCH", " reach "],
        }
    ).callsign_substrings == ["RCH", "REACH"]


def test_conflicting_lists_are_preserved(tmp_path):
    settings = AdsbSettingsStore(tmp_path / "a.json").update(
        {
            "include_hexes": ["00AB12"],
            "exclude_hexes": ["00ab12"],
        }
    )
    assert settings.include_hexes == settings.exclude_hexes == ["00AB12"]


def test_reopened_store_keeps_revision_and_settings(tmp_path):
    path = tmp_path / "a.json"
    saved = AdsbSettingsStore(path).update({"enabled": True})
    assert AdsbSettingsStore(path).get() == saved


def test_two_store_instances_merge_under_lock(tmp_path):
    path = tmp_path / "a.json"
    stores = [AdsbSettingsStore(path), AdsbSettingsStore(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(stores[0].update, {"include_hexes": ["000001"]}),
            pool.submit(stores[1].update, {"exclude_hexes": ["000002"]}),
        ]
        for job in jobs:
            job.result()
    result = stores[0].get()
    assert result.include_hexes == ["000001"]
    assert result.exclude_hexes == ["000002"]
    assert result.revision == 2


def test_corrupt_settings_are_not_replaced(tmp_path):
    path = tmp_path / "a.json"
    path.write_text("{broken")
    store = AdsbSettingsStore(path)
    with pytest.raises(ValueError):
        store.update({"enabled": True})
    assert path.read_text() == "{broken"


def test_failed_replace_preserves_revision_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "a.json"
    store = AdsbSettingsStore(path)
    saved = store.update({"enabled": True})
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("app.services.overview_adsb_settings.os.replace", fail)
    with pytest.raises(OSError):
        store.update({"enabled": False})
    assert path.read_bytes() == before
    assert store.get() == saved
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "payload", [{"revision": -1}, {"enabled": "false"}, {"unknown": True}]
)
def test_invalid_persisted_state_is_not_defaulted(tmp_path, payload):
    path = tmp_path / "a.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        AdsbSettingsStore(path).get()
