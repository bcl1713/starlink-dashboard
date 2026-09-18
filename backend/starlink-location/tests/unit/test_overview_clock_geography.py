from app.services.overview_clock_geography import OfflineClockGeography
from app.services.overview_clock_location import (
    ClockLocation,
    resolve_clock_location,
)


def test_resolves_omaha_with_offline_geographic_data():
    geography = OfflineClockGeography()
    assert geography.time_zone_at(41.2565, -95.9345) == "America/Chicago"
    assert geography.locality_at(41.2565, -95.9345) == {
        "city": "Omaha",
        "country_code": "US",
        "admin1": "NE",
    }


def test_resolves_washington_dc_with_us_postal_label_data():
    geography = OfflineClockGeography()
    assert geography.time_zone_at(38.9072, -77.0369) == "America/New_York"
    assert geography.locality_at(38.9072, -77.0369) == {
        "city": "Washington",
        "country_code": "US",
        "admin1": "DC",
    }


def test_offline_geography_integrates_with_clock_location_resolver():
    geography = OfflineClockGeography()
    result = resolve_clock_location(
        38.9072,
        -77.0369,
        time_zone_lookup=geography.time_zone_at,
        locality_lookup=geography.locality_at,
    )
    assert result == ClockLocation(
        time_zone="America/New_York",
        label="Washington, DC",
    )
