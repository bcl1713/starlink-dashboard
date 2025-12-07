"""Unit tests for satellite catalog management."""

import tempfile
from pathlib import Path


from app.satellites.catalog import Satellite, SatelliteCatalog, load_satellite_catalog


class TestSatellite:
    """Test individual satellite objects."""

    def test_satellite_creation(self):
        """Test basic satellite creation."""
        sat = Satellite(
            satellite_id="X-1",
            transport="X",
            longitude=120.0,
            slot="X-Slot-1",
        )

        assert sat.satellite_id == "X-1"
        assert sat.transport == "X"
        assert sat.longitude == 120.0

    def test_satellite_with_coverage_path(self):
        """Test satellite with coverage file."""
        coverage_path = Path("/tmp/coverage.geojson")

        sat = Satellite(
            satellite_id="AOR",
            transport="Ka",
            longitude=154.0,
            coverage_geojson_path=coverage_path,
        )

        assert sat.coverage_geojson_path == coverage_path
        assert sat.coverage_polygon is None  # Not loaded yet

    def test_satellite_optional_fields(self):
        """Test satellite with optional fields."""
        sat = Satellite(
            satellite_id="Ku-Leo",
            transport="Ku",
        )

        assert sat.satellite_id == "Ku-Leo"
        assert sat.longitude is None
        assert sat.slot is None
        assert sat.coverage_geojson_path is None


class TestSatelliteCatalog:
    """Test satellite catalog."""

    def test_catalog_creation(self):
        """Test empty catalog creation."""
        catalog = SatelliteCatalog()

        assert len(catalog.satellites) == 0
        assert len(catalog.list_all()) == 0

    def test_add_satellite(self):
        """Test adding satellite to catalog."""
        catalog = SatelliteCatalog()

        sat = Satellite(
            satellite_id="X-1",
            transport="X",
            longitude=120.0,
        )

        catalog.add_satellite(sat)

        assert len(catalog.satellites) == 1
        assert catalog.get_satellite("X-1") == sat

    def test_get_by_transport(self):
        """Test retrieving satellites by transport."""
        catalog = SatelliteCatalog()

        # Add multiple X satellites
        for i in range(1, 4):
            catalog.add_satellite(
                Satellite(
                    satellite_id=f"Ka-Custom-{i}",
                    transport="Ka",
                    longitude=100.0 + i * 10,
                )
            )

        ka_sats = catalog.get_by_transport("Ka")
        assert len(ka_sats) == 3
        assert all(sat.transport == "Ka" for sat in ka_sats)

    def test_validate_satellite(self):
        """Test satellite validation."""
        catalog = SatelliteCatalog()

        sat = Satellite(satellite_id="X-1", transport="X")
        catalog.add_satellite(sat)

        assert catalog.validate_satellite("X-1")
        assert not catalog.validate_satellite("X-2")

    def test_list_all_satellites(self):
        """Test listing all satellites."""
        catalog = SatelliteCatalog()

        # Add mix of transports
        catalog.add_satellite(Satellite(satellite_id="X-1", transport="X"))
        catalog.add_satellite(Satellite(satellite_id="AOR", transport="Ka"))
        catalog.add_satellite(Satellite(satellite_id="Ku-Leo", transport="Ku"))

        all_sats = catalog.list_all()
        assert len(all_sats) == 3

        sat_ids = {sat.satellite_id for sat in all_sats}
        assert sat_ids == {"X-1", "AOR", "Ku-Leo"}

    def test_transport_index_isolation(self):
        """Test that transport index tracks satellites correctly."""
        catalog = SatelliteCatalog()

        # Add satellites
        catalog.add_satellite(Satellite(satellite_id="X-1", transport="X"))
        catalog.add_satellite(Satellite(satellite_id="X-2", transport="X"))
        catalog.add_satellite(Satellite(satellite_id="Ka-1", transport="Ka"))

        # Check counts
        x_sats = catalog.get_by_transport("X")
        ka_sats = catalog.get_by_transport("Ka")
        ku_sats = catalog.get_by_transport("Ku")

        assert len(x_sats) == 2
        assert len(ka_sats) == 1
        assert len(ku_sats) == 0


class TestLoadSatelliteCatalog:
    """Test catalog loading from files."""

    def test_load_default_catalog(self):
        """Test loading default catalog."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "satellites"
            sat_coverage_dir = Path(tmpdir) / "coverage"

            catalog = load_satellite_catalog(
                data_dir=data_dir,
                sat_coverage_dir=sat_coverage_dir,
            )

            # Should have default satellites
            for sat_id in ("X-1", "AOR", "POR", "IOR", "Ku-Leo"):
                assert catalog.validate_satellite(sat_id)

    def test_default_ka_satellites_have_color(self):
        """Test that default Ka satellites have proper color coding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "satellites"
            sat_coverage_dir = Path(tmpdir) / "coverage"

            catalog = load_satellite_catalog(
                data_dir=data_dir,
                sat_coverage_dir=sat_coverage_dir,
            )

            ka_sats = catalog.get_by_transport("Ka")
            assert len(ka_sats) == 3

            allowed_colors = {"#4CAF50", "#66BB6A", "#81C784"}
            for sat in ka_sats:
                assert sat.color in allowed_colors

    def test_x_satellite_has_red_color(self):
        """Test that X satellite has red color."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "satellites"
            sat_coverage_dir = Path(tmpdir) / "coverage"

            catalog = load_satellite_catalog(
                data_dir=data_dir,
                sat_coverage_dir=sat_coverage_dir,
            )

            x_sat = catalog.get_satellite("X-1")
            assert x_sat.color == "#FF6B6B"

    def test_directories_created_if_missing(self):
        """Test that catalog loading creates necessary directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "nonexistent" / "satellites"
            sat_coverage_dir = Path(tmpdir) / "nonexistent" / "coverage"

            assert not data_dir.exists()
            assert not sat_coverage_dir.exists()

            load_satellite_catalog(
                data_dir=data_dir,
                sat_coverage_dir=sat_coverage_dir,
            )

            # Should create directories
            assert data_dir.exists()
            assert sat_coverage_dir.exists()

    def test_catalog_singleton_pattern(self):
        """Test that get_satellite_catalog returns consistent instance."""
        from app.satellites import get_satellite_catalog

        # Reset global (would need to access private variable in real code)
        # For now just test consistency
        catalog1 = get_satellite_catalog()
        catalog2 = get_satellite_catalog()

        # Should be same object
        assert catalog1 is catalog2


class TestSatelliteDefaults:
    """Test default satellite definitions."""

    def test_x_satellite_properties(self):
        """Test X satellite default properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = load_satellite_catalog(
                data_dir=Path(tmpdir) / "sat",
                sat_coverage_dir=Path(tmpdir) / "cov",
            )

            x_sat = catalog.get_satellite("X-1")
            assert x_sat.transport == "X"
            assert x_sat.slot == "X-Slot-1"
            assert x_sat.longitude is None  # Planner-defined

    def test_ka_satellite_slots(self):
        """Test Ka satellite slot assignments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = load_satellite_catalog(
                data_dir=Path(tmpdir) / "sat",
                sat_coverage_dir=Path(tmpdir) / "cov",
            )

            aor = catalog.get_satellite("AOR")
            por = catalog.get_satellite("POR")
            ior = catalog.get_satellite("IOR")

            assert aor.slot == "Atlantic Ocean Region"
            assert por.slot == "Pacific Ocean Region"
            assert ior.slot == "Indian Ocean Region"

    def test_ku_satellite_properties(self):
        """Test Ku LEO satellite properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog = load_satellite_catalog(
                data_dir=Path(tmpdir) / "sat",
                sat_coverage_dir=Path(tmpdir) / "cov",
            )

            ku_sat = catalog.get_satellite("Ku-Leo")
            assert ku_sat.transport == "Ku"
            assert ku_sat.longitude is None  # LEO, no fixed longitude
            assert ku_sat.slot == "LEO-Constellation"
