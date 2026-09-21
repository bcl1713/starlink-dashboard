from app.models.route import RoutePoint
from app.services.mission_clock_service import (
    apply_mission_activation_clock_settings,
    apply_mission_deactivation_clock_settings,
)
from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import OverviewClockSettingsStore


def test_activation_resolves_route_endpoints_and_persists_mission_clock_slots(
    tmp_path,
):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    original_clocks = [
        ClockLocation(
            label="Zulu Custom",
            time_zone="UTC",
        ),
        ClockLocation(
            label="Denver, CO",
            time_zone="America/Denver",
        ),
        ClockLocation(
            label="Manual Takeoff",
            time_zone="America/Los_Angeles",
        ),
        ClockLocation(
            label="Manual Landing",
            time_zone="Europe/London",
        ),
    ]
    store.set_clocks(original_clocks)
    takeoff_clock = ClockLocation(
        label="Washington, DC",
        time_zone="America/New_York",
    )
    landing_clock = ClockLocation(
        label="Paris, FR",
        time_zone="Europe/Paris",
    )

    def resolve_location(latitude: float, longitude: float) -> ClockLocation | None:
        if (latitude, longitude) == (38.9072, -77.0369):
            return takeoff_clock
        if (latitude, longitude) == (48.8566, 2.3522):
            return landing_clock
        raise AssertionError("only route endpoints may be resolved")

    result = apply_mission_activation_clock_settings(
        store,
        route_points=[
            RoutePoint(
                latitude=38.9072,
                longitude=-77.0369,
            ),
            RoutePoint(
                latitude=45.0,
                longitude=-30.0,
            ),
            RoutePoint(
                latitude=48.8566,
                longitude=2.3522,
            ),
        ],
        resolve_location=resolve_location,
    )
    expected_clocks = [
        original_clocks[0],
        original_clocks[1],
        takeoff_clock,
        landing_clock,
    ]
    assert result == expected_clocks
    assert store.get_clocks() == expected_clocks


def test_deactivation_restores_mission_clock_defaults_in_the_store(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    original_clocks = [
        ClockLocation(
            label="Zulu Custom",
            time_zone="UTC",
        ),
        ClockLocation(
            label="Denver, CO",
            time_zone="America/Denver",
        ),
        ClockLocation(
            label="Washington, DC",
            time_zone="America/New_York",
        ),
        ClockLocation(
            label="Paris, FR",
            time_zone="Europe/Paris",
        ),
    ]
    store.set_clocks(original_clocks)
    result = apply_mission_deactivation_clock_settings(store)
    expected_clocks = [
        original_clocks[0],
        original_clocks[1],
        ClockLocation(
            label="Omaha, NE",
            time_zone="America/Chicago",
        ),
        ClockLocation(
            label="Tokyo, JP",
            time_zone="Asia/Tokyo",
        ),
    ]
    assert result == expected_clocks
    assert store.get_clocks() == expected_clocks
