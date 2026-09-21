import pytest
from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import OverviewClockSettingsStore


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
