import json
import subprocess
import sys
import textwrap

from app.services.overview_clock_geography import OfflineClockGeography
from app.services.overview_clock_location import (
    ClockLocation,
    resolve_clock_location,
)


def test_locality_lookups_do_not_start_processes_with_an_active_thread():
    # A fresh interpreter prevents reverse_geocoder's singleton from hiding an
    # unsafe first lookup because another test already initialized its mode.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import json
                import threading
                from unittest.mock import patch

                from app.services.overview_clock_geography import OfflineClockGeography

                geography = OfflineClockGeography()
                release = threading.Event()
                thread = threading.Thread(target=release.wait)
                thread.start()
                try:
                    assert thread.is_alive()
                    # Keep real packaged data and queries; fail before an unsafe
                    # child can inherit the live application's threads/locks.
                    with patch(
                        "multiprocessing.process.BaseProcess.start",
                        side_effect=AssertionError("locality lookup started a child process"),
                    ):
                        locations = [
                            geography.locality_at(41.2565, -95.9345),
                            geography.locality_at(38.9072, -77.0369),
                            geography.locality_at(35.6762, 139.6503),
                            OfflineClockGeography().locality_at(41.2565, -95.9345),
                        ]
                    print(json.dumps(locations))
                finally:
                    release.set()
                    thread.join(timeout=5)
                    assert not thread.is_alive()
                """),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # The dependency may print a one-time packaged-data loading message.
    assert json.loads(result.stdout.splitlines()[-1]) == [
        {"city": "Omaha", "country_code": "US", "admin1": "NE"},
        {"city": "Washington", "country_code": "US", "admin1": "DC"},
        {"city": "Tokyo", "country_code": "JP", "admin1": "Tokyo"},
        {"city": "Omaha", "country_code": "US", "admin1": "NE"},
    ]


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
