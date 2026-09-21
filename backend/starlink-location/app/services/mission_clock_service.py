import logging
from collections.abc import Callable, Sequence

from app.models.route import RoutePoint
from app.services.mission_clock_endpoints import resolve_mission_endpoint_clocks
from app.services.mission_clock_settings import (
    apply_mission_activation_clock_overrides,
    apply_mission_deactivation_clock_resets,
)
from app.services.overview_clock_location import ClockLocation
from app.services.overview_clock_settings import OverviewClockSettingsStore

logger = logging.getLogger(__name__)


def persist_mission_clock_settings_best_effort(
    persist_settings: Callable[[], object],
    *,
    lifecycle_event: str,
) -> None:
    """Attempt ancillary clock persistence without changing lifecycle results."""
    try:
        persist_settings()
    except OSError:
        logger.warning(
            "Could not persist overview clock settings after %s",
            lifecycle_event,
        )


def apply_mission_activation_clock_settings(
    store: OverviewClockSettingsStore,
    *,
    route_points: Sequence[RoutePoint],
    resolve_location: Callable[[float, float], ClockLocation | None],
) -> list[ClockLocation]:
    """Resolve route endpoints and persist their mission-clock overrides."""
    takeoff_clock, landing_clock = resolve_mission_endpoint_clocks(
        route_points,
        resolve_location=resolve_location,
    )
    updated_clocks = apply_mission_activation_clock_overrides(
        store.get_clocks(),
        takeoff_clock=takeoff_clock,
        landing_clock=landing_clock,
    )
    store.set_clocks(updated_clocks)
    return updated_clocks


def apply_mission_deactivation_clock_settings(
    store: OverviewClockSettingsStore,
) -> list[ClockLocation]:
    """Restore mission-clock defaults and persist the updated collection."""
    updated_clocks = apply_mission_deactivation_clock_resets(
        store.get_clocks(),
    )
    store.set_clocks(updated_clocks)
    return updated_clocks
