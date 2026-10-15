from collections.abc import Callable, Mapping
from dataclasses import dataclass

TIME_ZONE_REPRESENTATIVE_LABELS = {
    "Asia/Tokyo": "Tokyo, JP",
    "America/Chicago": "Omaha, NE",
}


@dataclass(frozen=True)
class ClockLocation:
    time_zone: str
    label: str


def resolve_clock_location(
    latitude: float,
    longitude: float,
    *,
    time_zone_lookup: Callable[[float, float], str | None],
    locality_lookup: Callable[[float, float], Mapping[str, str] | None],
) -> ClockLocation | None:
    """Resolve one endpoint with injected offline geographic lookups."""

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    time_zone = time_zone_lookup(latitude, longitude)
    if time_zone is None:
        return None
    locality = locality_lookup(latitude, longitude)
    if locality is None:
        return ClockLocation(
            time_zone=time_zone,
            label=TIME_ZONE_REPRESENTATIVE_LABELS.get(time_zone, time_zone),
        )
    if locality["country_code"] == "US":
        label = f"{locality['city']}, {locality['admin1']}"
    else:
        label = f"{locality['city']}, {locality['country_code']}"
    return ClockLocation(time_zone=time_zone, label=label)
