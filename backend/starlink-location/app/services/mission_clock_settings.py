from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import DEFAULT_OVERVIEW_CLOCKS


def apply_mission_activation_clock_overrides(
    current_clocks: list[ClockLocation],
    *,
    takeoff_clock: ClockLocation | None,
    landing_clock: ClockLocation | None,
) -> list[ClockLocation]:
    """Preserve fixed clocks and replace the two mission-derived slots."""
    return [
        current_clocks[0],
        current_clocks[1],
        takeoff_clock or DEFAULT_OVERVIEW_CLOCKS[2],
        landing_clock or DEFAULT_OVERVIEW_CLOCKS[3],
    ]


def apply_mission_deactivation_clock_resets(
    current_clocks: list[ClockLocation],
) -> list[ClockLocation]:
    """Preserve fixed clocks and restore the two mission slots to defaults."""
    return apply_mission_activation_clock_overrides(
        current_clocks,
        takeoff_clock=None,
        landing_clock=None,
    )
