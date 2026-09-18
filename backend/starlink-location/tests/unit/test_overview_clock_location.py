from app.services.overview_clock_location import (
    ClockLocation,
    resolve_clock_location,
)


def test_resolves_omaha_endpoint_to_timezone_and_city_state_label():
    result = resolve_clock_location(
        41.2565,
        -95.9345,
        time_zone_lookup=lambda latitude, longitude: "America/Chicago",
        locality_lookup=lambda latitude, longitude: {
            "city": "Omaha",
            "country_code": "US",
            "admin1": "NE",
        },
    )
    assert result == ClockLocation(
        time_zone="America/Chicago",
        label="Omaha, NE",
    )


def test_resolves_paris_endpoint_to_timezone_and_city_country_label():
    result = resolve_clock_location(
        48.8566,
        2.3522,
        time_zone_lookup=lambda latitude, longitude: "Europe/Paris",
        locality_lookup=lambda latitude, longitude: {
            "city": "Paris",
            "country_code": "FR",
        },
    )
    assert result == ClockLocation(
        time_zone="Europe/Paris",
        label="Paris, FR",
    )


def test_uses_representative_when_locality_is_unavailable_in_tokyo():
    result = resolve_clock_location(
        35.6762,
        139.6503,
        time_zone_lookup=lambda latitude, longitude: "Asia/Tokyo",
        locality_lookup=lambda latitude, longitude: None,
    )
    assert result == ClockLocation(
        time_zone="Asia/Tokyo",
        label="Tokyo, JP",
    )


def test_uses_representative_when_locality_is_unavailable_in_omaha():
    result = resolve_clock_location(
        41.2565,
        -95.9345,
        time_zone_lookup=lambda latitude, longitude: "America/Chicago",
        locality_lookup=lambda latitude, longitude: None,
    )
    assert result == ClockLocation(
        time_zone="America/Chicago",
        label="Omaha, NE",
    )
