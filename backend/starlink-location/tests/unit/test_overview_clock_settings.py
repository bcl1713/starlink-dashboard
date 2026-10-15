import json

import pytest

from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import (
    DEFAULT_OVERVIEW_CLOCKS,
    OverviewClockSettingsStore,
)


def test_returns_the_four_default_operational_clocks(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    assert store.get_clocks() == [
        ClockLocation(
            label="Zulu / UTC",
            time_zone="UTC",
        ),
        ClockLocation(
            label="Washington, DC",
            time_zone="America/New_York",
        ),
        ClockLocation(
            label="Omaha, NE",
            time_zone="America/Chicago",
        ),
        ClockLocation(
            label="Tokyo, JP",
            time_zone="Asia/Tokyo",
        ),
    ]


def test_persists_operator_clock_edits_across_store_instances(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    store = OverviewClockSettingsStore(path)
    clocks = store.get_clocks()
    clocks[1] = ClockLocation(
        label="Houston, TX",
        time_zone="America/Chicago",
    )
    store.set_clocks(clocks)
    reopened_store = OverviewClockSettingsStore(path)
    assert reopened_store.get_clocks() == clocks


def test_returns_defaults_when_persisted_settings_are_partial_json(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    path.write_text('{"clocks": [')

    assert OverviewClockSettingsStore(path).get_clocks() == list(
        DEFAULT_OVERVIEW_CLOCKS
    )


def test_returns_defaults_when_persisted_clock_label_is_not_a_string(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    path.write_text(
        json.dumps(
            {
                "clocks": [
                    {"label": 1, "time_zone": "UTC"},
                    {"label": "Washington, DC", "time_zone": "America/New_York"},
                    {"label": "Omaha, NE", "time_zone": "America/Chicago"},
                    {"label": "Tokyo, JP", "time_zone": "Asia/Tokyo"},
                ]
            }
        )
    )

    assert OverviewClockSettingsStore(path).get_clocks() == list(
        DEFAULT_OVERVIEW_CLOCKS
    )


def test_returns_defaults_when_persisted_clock_timezone_is_not_a_string(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    path.write_text(
        json.dumps(
            {
                "clocks": [
                    {"label": "Zulu / UTC", "time_zone": ["UTC"]},
                    {"label": "Washington, DC", "time_zone": "America/New_York"},
                    {"label": "Omaha, NE", "time_zone": "America/Chicago"},
                    {"label": "Tokyo, JP", "time_zone": "Asia/Tokyo"},
                ]
            }
        )
    )

    assert OverviewClockSettingsStore(path).get_clocks() == list(
        DEFAULT_OVERVIEW_CLOCKS
    )


def test_returns_defaults_when_persisted_clock_timezone_is_invalid(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    path.write_text(
        json.dumps(
            {
                "clocks": [
                    {"label": "Zulu / UTC", "time_zone": "Mars/Olympus"},
                    {"label": "Washington, DC", "time_zone": "America/New_York"},
                    {"label": "Omaha, NE", "time_zone": "America/Chicago"},
                    {"label": "Tokyo, JP", "time_zone": "Asia/Tokyo"},
                ]
            }
        )
    )

    assert OverviewClockSettingsStore(path).get_clocks() == list(
        DEFAULT_OVERVIEW_CLOCKS
    )


def test_failed_replacement_preserves_existing_clocks_and_cleans_temp_file(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "overview_clock_settings.json"
    store = OverviewClockSettingsStore(path)
    existing_clocks = store.get_clocks()
    store.set_clocks(existing_clocks)
    persisted_collection = json.loads(path.read_text())
    replacement_clocks = [
        ClockLocation(label="Zulu / UTC", time_zone="UTC"),
        ClockLocation(label="Houston, TX", time_zone="America/Chicago"),
        ClockLocation(label="Omaha, NE", time_zone="America/Chicago"),
        ClockLocation(label="Tokyo, JP", time_zone="Asia/Tokyo"),
    ]

    def fail_replacement(*_args):
        raise OSError("disk replaced by gremlins")

    monkeypatch.setattr(
        "app.services.overview_clock_settings.os.replace",
        fail_replacement,
    )

    with pytest.raises(OSError, match="disk replaced by gremlins"):
        store.set_clocks(replacement_clocks)

    assert json.loads(path.read_text()) == persisted_collection
    assert OverviewClockSettingsStore(path).get_clocks() == existing_clocks
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_rejects_saving_anything_other_than_four_clocks(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    with pytest.raises(ValueError, match="Exactly four clocks are required"):
        store.set_clocks(store.get_clocks()[:3])


def test_rejects_an_invalid_iana_timezone(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    clocks = store.get_clocks()
    clocks[0] = ClockLocation(
        label="Zulu / UTC",
        time_zone="Mars/Olympus",
    )
    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        store.set_clocks(clocks)


def test_rejects_a_blank_clock_label(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    clocks = store.get_clocks()
    clocks[0] = ClockLocation(
        label="   ",
        time_zone="UTC",
    )
    with pytest.raises(ValueError, match="Clock labels must not be blank"):
        store.set_clocks(clocks)
