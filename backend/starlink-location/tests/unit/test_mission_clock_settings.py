from app.services.mission_clock_service import (
    persist_mission_clock_settings_best_effort,
)
from app.services.mission_clock_settings import (
    apply_mission_activation_clock_overrides,
    apply_mission_deactivation_clock_resets,
)
from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import DEFAULT_OVERVIEW_CLOCKS


def test_activation_preserves_first_two_clocks_and_replaces_mission_slots():
    current_clocks = [
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
    takeoff_clock = ClockLocation(
        label="Washington, DC",
        time_zone="America/New_York",
    )
    landing_clock = ClockLocation(
        label="Paris, FR",
        time_zone="Europe/Paris",
    )
    result = apply_mission_activation_clock_overrides(
        current_clocks,
        takeoff_clock=takeoff_clock,
        landing_clock=landing_clock,
    )
    assert result == [
        current_clocks[0],
        current_clocks[1],
        takeoff_clock,
        landing_clock,
    ]


def test_activation_uses_slot_defaults_when_endpoint_locations_are_unavailable():
    current_clocks = [
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
    result = apply_mission_activation_clock_overrides(
        current_clocks,
        takeoff_clock=None,
        landing_clock=None,
    )
    assert result == [
        current_clocks[0],
        current_clocks[1],
        DEFAULT_OVERVIEW_CLOCKS[2],
        DEFAULT_OVERVIEW_CLOCKS[3],
    ]


def test_clock_write_oserror_is_logged_and_does_not_escape(caplog):
    def fail_clock_write():
        raise OSError("read-only filesystem")

    persist_mission_clock_settings_best_effort(
        fail_clock_write,
        lifecycle_event="activating a mission",
    )

    assert (
        "Could not persist overview clock settings after activating a mission"
        in caplog.text
    )


def test_deactivation_preserves_first_two_clocks_and_resets_mission_slots():
    current_clocks = [
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
    result = apply_mission_deactivation_clock_resets(current_clocks)
    assert result == [
        current_clocks[0],
        current_clocks[1],
        DEFAULT_OVERVIEW_CLOCKS[2],
        DEFAULT_OVERVIEW_CLOCKS[3],
    ]
