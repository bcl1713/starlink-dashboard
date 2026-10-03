import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier, Event

import pytest
from filelock import FileLock

from app.services.overview_link_settings import (
    OverviewLinkSettings,
    OverviewLinkSettingsStore,
)


def test_missing_file_returns_immutable_enabled_defaults(tmp_path):
    store = OverviewLinkSettingsStore(tmp_path / "nested/settings/overview-links.json")
    settings = store.get()
    assert settings.starshield_link_enabled is True
    assert settings.x_band_link_enabled is True
    with pytest.raises(FrozenInstanceError):
        settings.starshield_link_enabled = False


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({}, OverviewLinkSettings(True, True)),
        ({"starshield_link_enabled": False}, OverviewLinkSettings(False, True)),
        ({"x_band_link_enabled": False}, OverviewLinkSettings(True, False)),
    ],
)
def test_missing_fields_default_without_overwriting_false(tmp_path, payload, expected):
    path = tmp_path / "overview-links.json"
    path.write_text(json.dumps(payload))
    store = OverviewLinkSettingsStore(path)
    assert store.get() == expected
    assert store.update({"x_band_link_enabled": False}) == OverviewLinkSettings(
        expected.starshield_link_enabled, False
    )


@pytest.mark.parametrize("starshield", [True, False])
@pytest.mark.parametrize("x_band", [True, False])
def test_all_pairs_survive_store_recreation(tmp_path, starshield, x_band):
    path = tmp_path / "nested/settings/overview-links.json"
    payload = {
        "starshield_link_enabled": starshield,
        "x_band_link_enabled": x_band,
    }
    assert OverviewLinkSettingsStore(path).update(payload) == OverviewLinkSettings(
        starshield, x_band
    )
    assert json.loads(path.read_text()) == payload
    assert OverviewLinkSettingsStore(path).get() == OverviewLinkSettings(
        starshield, x_band
    )


def test_disjoint_updates_preserve_both_switches(tmp_path, monkeypatch):
    path = tmp_path / "overview-links.json"
    store = OverviewLinkSettingsStore(path)
    store.update({"starshield_link_enabled": True, "x_band_link_enabled": True})
    barrier = Barrier(2)
    original_load = json.load

    def slow_read(handle):
        payload = original_load(handle)
        # Expose a lost-update race if the read is moved outside the merge lock.
        time.sleep(0.03)
        return payload

    monkeypatch.setattr("app.services.overview_link_settings.json.load", slow_read)

    def update(field):
        other_viewer = OverviewLinkSettingsStore(path)
        barrier.wait(timeout=5)
        return other_viewer.update({field: False})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(update, field)
            for field in ("starshield_link_enabled", "x_band_link_enabled")
        ]
        for future in futures:
            future.result(timeout=5)
    assert store.get().starshield_link_enabled is False
    assert store.get().x_band_link_enabled is False


@pytest.mark.parametrize("operation", ["get", "update"])
def test_reads_and_updates_respect_another_store_file_lock(tmp_path, operation):
    path = tmp_path / "overview-links.json"
    store = OverviewLinkSettingsStore(path)
    started, finished = Event(), Event()

    def access():
        started.set()
        result = (
            store.get()
            if operation == "get"
            else store.update({"starshield_link_enabled": False})
        )
        finished.set()
        return result

    with ThreadPoolExecutor(max_workers=1) as executor:
        with FileLock(f"{path}.lock"):
            future = executor.submit(access)
            assert started.wait(timeout=5)
            assert not finished.wait(timeout=0.1)
        result = future.result(timeout=5)
    assert result.starshield_link_enabled is (operation == "get")


@pytest.mark.parametrize(
    "contents",
    [
        '{"starshield_link_enabled":',
        "null",
        "[]",
        '{"starshield_link_enabled": null}',
        '{"starshield_link_enabled": 0}',
        '{"x_band_link_enabled": "false"}',
        '{"x_band_link_enabled": []}',
        '{"unexpected": true}',
    ],
)
def test_invalid_disk_settings_raise_without_replacing_contents(tmp_path, contents):
    path = tmp_path / "overview-links.json"
    path.write_text(contents)
    store = OverviewLinkSettingsStore(path)
    with pytest.raises((ValueError, TypeError)):
        store.get()
    with pytest.raises((ValueError, TypeError)):
        store.update({"starshield_link_enabled": False})
    assert path.read_text() == contents


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"unknown": True},
        {"starshield_link_enabled": None},
        {"starshield_link_enabled": 0},
        {"x_band_link_enabled": "false"},
    ],
)
def test_invalid_updates_preserve_saved_pair(tmp_path, changes):
    path = tmp_path / "overview-links.json"
    store = OverviewLinkSettingsStore(path)
    store.update({"starshield_link_enabled": False})
    original = path.read_bytes()
    with pytest.raises((ValueError, TypeError)):
        store.update(changes)
    assert path.read_bytes() == original


def test_failed_atomic_replace_preserves_last_good_pair_and_cleans_temp(
    tmp_path, monkeypatch
):
    path = tmp_path / "overview-links.json"
    store = OverviewLinkSettingsStore(path)
    store.update({"starshield_link_enabled": False})
    original = path.read_bytes()

    def fail_replace(*args):
        raise OSError("disk write failed")

    monkeypatch.setattr("app.services.overview_link_settings.os.replace", fail_replace)
    with pytest.raises(OSError, match="disk write failed"):
        store.update({"x_band_link_enabled": False})
    assert path.read_bytes() == original
    assert OverviewLinkSettingsStore(path).get() == OverviewLinkSettings(False, True)
    assert list(tmp_path.glob("*.tmp")) == []
