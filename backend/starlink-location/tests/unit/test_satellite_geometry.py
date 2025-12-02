"""Unit tests for satellite geometry calculations.

Tests azimuth/elevation calculations, ECEF conversions, and look angle computations
against known reference values.
"""

import math


from app.satellites.geometry import (
    GEOSTATIONARY_ALTITUDE,
    WGS84_SEMI_MAJOR_AXIS,
    azimuth_elevation_from_ecef,
    ecef_from_geodetic,
    geodetic_from_ecef,
    is_in_azimuth_range,
    look_angles,
)


class TestEcefConversion:
    """Test geodetic <-> ECEF coordinate conversions."""

    def test_ecef_from_geodetic_origin(self):
        """Test conversion at equator and prime meridian."""
        # At equator (0, 0) on sea level: X should be semi-major axis
        x, y, z = ecef_from_geodetic(0.0, 0.0, 0.0)

        assert abs(x - WGS84_SEMI_MAJOR_AXIS) < 1.0
        assert abs(y) < 1.0
        assert abs(z) < 1.0

    def test_ecef_from_geodetic_north_pole(self):
        """Test conversion at North Pole."""
        # At North Pole: X and Y should be 0, Z should be semi-minor axis
        x, y, z = ecef_from_geodetic(90.0, 0.0, 0.0)

        assert abs(x) < 1.0
        assert abs(y) < 1.0
        assert abs(z - 6356752.3) < 1.0  # semi-minor axis

    def test_ecef_from_geodetic_south_pole(self):
        """Test conversion at South Pole."""
        x, y, z = ecef_from_geodetic(-90.0, 0.0, 0.0)

        assert abs(x) < 1.0
        assert abs(y) < 1.0
        assert abs(z + 6356752.3) < 1.0  # Negative semi-minor axis

    def test_ecef_from_geodetic_with_altitude(self):
        """Test conversion with altitude component."""
        altitude = 10000.0  # 10 km altitude

        x1, y1, z1 = ecef_from_geodetic(0.0, 0.0, 0.0)
        x2, y2, z2 = ecef_from_geodetic(0.0, 0.0, altitude)

        # Point at altitude should be further from origin
        r1 = math.sqrt(x1**2 + y1**2 + z1**2)
        r2 = math.sqrt(x2**2 + y2**2 + z2**2)

        assert r2 > r1
        assert abs((r2 - r1) - altitude) < 1.0  # Should be close to altitude difference

    def test_geodetic_from_ecef_roundtrip(self):
        """Test roundtrip conversion geodetic -> ECEF -> geodetic."""
        test_cases = [
            (0.0, 0.0, 0.0),  # Equator, prime meridian
            (45.0, 120.0, 1000.0),  # Arbitrary point
            (-45.0, -120.0, 5000.0),  # Southern hemisphere
            (89.9, 180.0, 0.0),  # Near North Pole
        ]

        for lat, lon, alt in test_cases:
            x, y, z = ecef_from_geodetic(lat, lon, alt)
            lat2, lon2, alt2 = geodetic_from_ecef(x, y, z)

            # Normalize longitudes to -180..180
            lon = (lon + 180) % 360 - 180
            lon2 = (lon2 + 180) % 360 - 180

            assert abs(lat - lat2) < 0.001, f"Latitude mismatch at ({lat}, {lon})"
            assert abs(lon - lon2) < 0.001, f"Longitude mismatch at ({lat}, {lon})"
            assert abs(alt - alt2) < 1.0, f"Altitude mismatch at ({lat}, {lon})"


class TestLookAngles:
    """Test azimuth and elevation calculations."""

    def test_look_angles_at_equator_same_longitude(self):
        """Test look angles when aircraft and satellite at same longitude."""
        # Aircraft at equator below geostationary satellite
        azimuth, elevation = look_angles(
            aircraft_lat_deg=0.0,
            aircraft_lon_deg=0.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # Should be directly overhead (south azimuth, high elevation)
        assert elevation > 80.0  # Nearly zenith
        assert abs(azimuth - 180.0) < 1.0 or abs(azimuth) < 1.0  # South or North

    def test_look_angles_aircraft_north_of_satellite(self):
        """Test look angles when aircraft is north of satellite."""
        azimuth, elevation = look_angles(
            aircraft_lat_deg=45.0,
            aircraft_lon_deg=0.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # Satellite to south, lower elevation
        assert elevation < 60.0
        assert elevation > 0.0  # Still visible (above horizon)
        assert abs(azimuth - 180.0) < 5.0  # South direction

    def test_look_angles_aircraft_east_of_satellite(self):
        """Test look angles when aircraft is east of satellite."""
        azimuth, elevation = look_angles(
            aircraft_lat_deg=0.0,
            aircraft_lon_deg=10.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # Satellite to west, can still have good elevation at equator
        assert elevation > 0.0  # Visible (above horizon)
        assert abs(azimuth - 270.0) < 5.0  # West direction

    def test_look_angles_with_altitude(self):
        """Test that altitude affects look angles (effect direction depends on position)."""
        alt_low = 0.0
        alt_high = 50000.0  # 50 km

        # Aircraft far from satellite
        az1, el1 = look_angles(
            aircraft_lat_deg=60.0,
            aircraft_lon_deg=0.0,
            aircraft_alt_m=alt_low,
            satellite_lon_deg=0.0,
        )

        az2, el2 = look_angles(
            aircraft_lat_deg=60.0,
            aircraft_lon_deg=0.0,
            aircraft_alt_m=alt_high,
            satellite_lon_deg=0.0,
        )

        # Altitude affects look angles (elevation changes)
        # At high latitudes, higher altitude can decrease apparent elevation
        assert el1 != el2  # Altit makes a difference

    def test_look_angles_horizon_check(self):
        """Test that satellite below horizon has negative elevation."""
        # Aircraft far from satellite (should be below horizon)
        azimuth, elevation = look_angles(
            aircraft_lat_deg=85.0,  # Very far from geostationary
            aircraft_lon_deg=0.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # At polar regions, geostationary satellites are typically below horizon
        assert (
            elevation < 0.0
        ), "Geostationary sat should be below horizon at high latitude"


class TestAzimuthElevationFromEcef:
    """Test lower-level ECEF-based azimuth/elevation calculation."""

    def test_azimuth_elevation_zenith(self):
        """Test when target is directly overhead (zenith)."""
        observer_ecef = (WGS84_SEMI_MAJOR_AXIS, 0.0, 0.0)
        target_ecef = (WGS84_SEMI_MAJOR_AXIS + 1000.0, 0.0, 0.0)

        azimuth, elevation = azimuth_elevation_from_ecef(
            observer_ecef, target_ecef, 0.0, 0.0
        )

        # Should be nearly zenith
        assert elevation > 85.0
        assert 0 <= azimuth < 360

    def test_azimuth_range_360_wrapping(self):
        """Test that azimuth wraps correctly (0-360)."""
        observer_ecef = (WGS84_SEMI_MAJOR_AXIS, 0.0, 0.0)
        # Target to the north
        target_ecef = (WGS84_SEMI_MAJOR_AXIS, 0.0, 1000000.0)

        azimuth, elevation = azimuth_elevation_from_ecef(
            observer_ecef, target_ecef, 0.0, 0.0
        )

        assert 0 <= azimuth < 360


class TestAzimuthRangeChecks:
    """Test azimuth range checking for forbidden cones."""

    def test_normal_azimuth_range_135_to_225(self):
        """Test normal ops forbidden cone (135-225 degrees)."""
        # Inside forbidden zone
        assert is_in_azimuth_range(180.0, 135.0, 225.0)
        assert is_in_azimuth_range(135.0, 135.0, 225.0)
        assert is_in_azimuth_range(225.0, 135.0, 225.0)

        # Outside forbidden zone
        assert not is_in_azimuth_range(90.0, 135.0, 225.0)
        assert not is_in_azimuth_range(270.0, 135.0, 225.0)

    def test_aar_azimuth_range_with_wraparound(self):
        """Test AAR forbidden cone (315-45 degrees, wraps around north)."""
        # Inside forbidden zone
        assert is_in_azimuth_range(0.0, 315.0, 45.0)
        assert is_in_azimuth_range(10.0, 315.0, 45.0)
        assert is_in_azimuth_range(315.0, 315.0, 45.0)
        assert is_in_azimuth_range(355.0, 315.0, 45.0)

        # Outside forbidden zone
        assert not is_in_azimuth_range(90.0, 315.0, 45.0)
        assert not is_in_azimuth_range(180.0, 315.0, 45.0)
        assert not is_in_azimuth_range(270.0, 315.0, 45.0)

    def test_azimuth_wraparound_edge_cases(self):
        """Test edge cases at 0/360 boundary."""
        # 0 degrees should be equivalent to 360
        assert is_in_azimuth_range(0.0, 315.0, 45.0)
        assert is_in_azimuth_range(360.0, 315.0, 45.0)

        # Negative azimuths should be normalized
        assert is_in_azimuth_range(-45.0, 315.0, 45.0)

    def test_non_wraparound_range(self):
        """Test normal range without wraparound."""
        # 90 to 180 (east to south)
        assert is_in_azimuth_range(90.0, 90.0, 180.0)
        assert is_in_azimuth_range(135.0, 90.0, 180.0)
        assert is_in_azimuth_range(180.0, 90.0, 180.0)

        assert not is_in_azimuth_range(45.0, 90.0, 180.0)
        assert not is_in_azimuth_range(225.0, 90.0, 180.0)


class TestGeometryEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_aircraft_at_antipode(self):
        """Test azimuth calculation with aircraft at antipodal point."""
        # Aircraft at South Pole, satellite at equator
        azimuth, elevation = look_angles(
            aircraft_lat_deg=-90.0,
            aircraft_lon_deg=0.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=180.0,
        )

        # Should be below horizon at pole
        assert elevation < 0.0

    def test_date_line_crossing(self):
        """Test calculation across International Date Line.

        Note: Azimuths can differ by 180° when viewing from opposite sides
        of a point, but elevations should be similar.
        """
        # Aircraft just west of IDL
        az1, el1 = look_angles(
            aircraft_lat_deg=0.0,
            aircraft_lon_deg=179.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # Aircraft just east of IDL (same longitude, different representation)
        az2, el2 = look_angles(
            aircraft_lat_deg=0.0,
            aircraft_lon_deg=-179.0,
            aircraft_alt_m=0.0,
            satellite_lon_deg=0.0,
        )

        # Elevations should be very similar (distance is same)
        assert abs(el1 - el2) < 1.0
        # Azimuths will differ by ~180° due to geometry (on opposite sides of point)
        az_diff = abs(az1 - az2)
        assert az_diff > 170 or az_diff < 10  # Either ~180° apart or same direction

    def test_geostationary_satellite_position(self):
        """Test that geostationary altitude is used correctly."""
        # Verify geostationary constant is defined
        assert GEOSTATIONARY_ALTITUDE > 35000000  # > 35,000 km
        assert GEOSTATIONARY_ALTITUDE < 36000000  # < 36,000 km


class TestPerformance:
    """Test performance characteristics of calculations."""

    def test_look_angles_performance(self):
        """Test that look angle calculation completes quickly."""
        import time

        # Run 1000 calculations
        start = time.time()
        for i in range(1000):
            look_angles(
                aircraft_lat_deg=30.0 + (i % 60 - 30) * 0.1,
                aircraft_lon_deg=0.0 + (i % 180 - 90) * 0.1,
                aircraft_alt_m=0.0,
                satellite_lon_deg=0.0,
            )
        elapsed = time.time() - start

        # Should complete 1000 calculations in less than 500ms
        assert (
            elapsed < 0.5
        ), f"Performance degradation: {elapsed:.3f}s for 1000 calculations"

    def test_ecef_conversion_performance(self):
        """Test that ECEF conversion completes quickly."""
        import time

        start = time.time()
        for i in range(1000):
            ecef_from_geodetic(
                latitude=30.0 + (i % 60 - 30) * 0.1,
                longitude=0.0 + (i % 360 - 180) * 0.1,
                altitude=0.0,
            )
        elapsed = time.time() - start

        # Should complete 1000 conversions in less than 200ms
        assert (
            elapsed < 0.2
        ), f"Performance degradation: {elapsed:.3f}s for 1000 conversions"
