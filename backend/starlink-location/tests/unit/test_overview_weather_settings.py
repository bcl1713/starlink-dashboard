"""Weather saves cannot enable implicitly or damage confirmed configuration."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.models.overview_weather import WeatherSettings
from app.services.overview_weather.settings import WeatherSettingsStore


def test_defaults_and_idempotent_save(tmp_path):
    path = tmp_path / "overview-weather.json"
    store = WeatherSettingsStore(path)
    assert store.get() == WeatherSettings(enabled=False, revision=0)
    assert not path.exists()
    assert store.update({"enabled": True}).revision == 1
    assert store.update({"enabled": True}).revision == 1
    assert WeatherSettingsStore(path).get().enabled is True
    assert store.update({"enabled": False}).revision == 2


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"revision": 1},
        {"enabled": None},
        {"enabled": "true"},
        {"enabled": 1},
        {"enabled": False, "extra": 1},
    ],
)
def test_rejects_unconfirmed_or_coerced_updates(tmp_path, changes):
    store = WeatherSettingsStore(tmp_path / "weather.json")
    with pytest.raises(ValidationError):
        store.update(changes)
    assert store.get().revision == 0


@pytest.mark.parametrize("operation", ["os.replace", "os.fsync"])
def test_failed_save_preserves_confirmed_bytes(tmp_path, operation):
    path = tmp_path / "weather.json"
    store = WeatherSettingsStore(path)
    store.update({"enabled": True})
    before = path.read_bytes()
    with patch(
        f"app.services.overview_weather.settings.{operation}",
        side_effect=OSError("unwritable"),
    ), pytest.raises(OSError):
        store.update({"enabled": False})
    assert path.read_bytes() == before
    assert store.get() == WeatherSettings(enabled=True, revision=1)
    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupt_saved_state_is_not_overwritten(tmp_path):
    path = tmp_path / "weather.json"
    path.write_text('{"enabled": "yes", "revision": 0}')
    store = WeatherSettingsStore(path)
    with pytest.raises(ValidationError):
        store.get()
    with pytest.raises(ValidationError):
        store.update({"enabled": True})
    assert '"yes"' in path.read_text()


def test_concurrent_same_value_writers_advance_once(tmp_path):
    path = tmp_path / "weather.json"
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: WeatherSettingsStore(path).update({"enabled": True}),
                range(16),
            )
        )
    assert {result.revision for result in results} == {1}
    assert WeatherSettingsStore(path).get().enabled is True
