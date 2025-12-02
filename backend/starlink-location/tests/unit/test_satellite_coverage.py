"""Unit tests for satellite coverage sampling."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


from app.satellites.coverage import CoverageEvent, CoverageSampler, point_in_polygon


class TestPointInPolygon:
    """Test point-in-polygon ray casting algorithm."""

    def test_point_inside_simple_square(self):
        """Test point clearly inside a square."""
        square = [
            (-1.0, -1.0),
            (1.0, -1.0),
            (1.0, 1.0),
            (-1.0, 1.0),
        ]

        assert point_in_polygon((0.0, 0.0), square)
        assert point_in_polygon((0.5, 0.5), square)
        assert point_in_polygon((-0.5, -0.5), square)

    def test_point_outside_simple_square(self):
        """Test point clearly outside a square."""
        square = [
            (-1.0, -1.0),
            (1.0, -1.0),
            (1.0, 1.0),
            (-1.0, 1.0),
        ]

        assert not point_in_polygon((2.0, 0.0), square)
        assert not point_in_polygon((0.0, 2.0), square)
        assert not point_in_polygon((2.0, 2.0), square)

    def test_point_on_polygon_edge(self):
        """Test point on polygon boundary (edge case)."""
        square = [
            (-1.0, -1.0),
            (1.0, -1.0),
            (1.0, 1.0),
            (-1.0, 1.0),
        ]

        # Points on edges (behavior may vary but should be consistent)
        result = point_in_polygon((0.0, 1.0), square)
        assert isinstance(result, bool)

    def test_point_at_polygon_vertex(self):
        """Test point at polygon vertex."""
        square = [
            (-1.0, -1.0),
            (1.0, -1.0),
            (1.0, 1.0),
            (-1.0, 1.0),
        ]

        result = point_in_polygon((-1.0, -1.0), square)
        assert isinstance(result, bool)

    def test_polygon_with_geographic_coords(self):
        """Test polygon in lat/lon coordinates."""
        # Rough rectangle around San Francisco Bay Area
        region = [
            (-122.0, 37.0),
            (-121.0, 37.0),
            (-121.0, 38.0),
            (-122.0, 38.0),
        ]

        # Point inside
        assert point_in_polygon((-121.5, 37.5), region)

        # Points outside
        assert not point_in_polygon((-120.0, 37.5), region)
        assert not point_in_polygon((-121.5, 39.0), region)

    def test_complex_polygon(self):
        """Test more complex polygon shape."""
        # L-shaped polygon
        l_shape = [
            (0.0, 0.0),
            (2.0, 0.0),
            (2.0, 1.0),
            (1.0, 1.0),
            (1.0, 2.0),
            (0.0, 2.0),
        ]

        # Inside the horizontal part
        assert point_in_polygon((1.0, 0.5), l_shape)

        # Inside the vertical part
        assert point_in_polygon((0.5, 1.5), l_shape)

        # Outside
        assert not point_in_polygon((1.5, 1.5), l_shape)


class TestCoverageEvent:
    """Test coverage event data structure."""

    def test_coverage_event_creation(self):
        """Test creating a coverage event."""
        now = datetime.utcnow()
        event = CoverageEvent(
            timestamp=now,
            event_type="entry",
            satellite_id="POR",
            latitude=30.0,
            longitude=120.0,
        )

        assert event.timestamp == now
        assert event.event_type == "entry"
        assert event.satellite_id == "POR"
        assert event.latitude == 30.0
        assert event.longitude == 120.0

    def test_coverage_event_with_metadata(self):
        """Test event with metadata."""
        now = datetime.utcnow()
        event = CoverageEvent(
            timestamp=now,
            event_type="exit",
            satellite_id="AOR",
            latitude=30.0,
            longitude=120.0,
            metadata={"reason": "scheduled maintenance"},
        )

        assert event.metadata["reason"] == "scheduled maintenance"


class TestCoverageSampler:
    """Test coverage sampling functionality."""

    def test_sampler_initialization(self):
        """Test creating a coverage sampler."""
        sampler = CoverageSampler()

        assert sampler.coverage_data is None
        assert len(sampler.satellite_polygons) == 0

    def test_load_simple_geojson(self):
        """Test loading simple GeoJSON coverage data."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "POR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.0, 37.0],
                                [-121.0, 37.0],
                                [-121.0, 38.0],
                                [-122.0, 38.0],
                                [-122.0, 37.0],
                            ]
                        ],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "coverage.geojson"
            with open(geojson_path, "w") as f:
                json.dump(geojson_data, f)

            sampler = CoverageSampler(geojson_path)

            assert "POR" in sampler.satellite_polygons
            assert len(sampler.satellite_polygons["POR"]) == 1

    def test_check_coverage_at_point_inside(self):
        """Test coverage check for point inside polygon."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "POR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.0, 37.0],
                                [-121.0, 37.0],
                                [-121.0, 38.0],
                                [-122.0, 38.0],
                                [-122.0, 37.0],
                            ]
                        ],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "coverage.geojson"
            with open(geojson_path, "w") as f:
                json.dump(geojson_data, f)

            sampler = CoverageSampler(geojson_path)

            # Point inside coverage
            covered = sampler.check_coverage_at_point(37.5, -121.5)
            assert "POR" in covered

    def test_check_coverage_at_point_outside(self):
        """Test coverage check for point outside polygon."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "POR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.0, 37.0],
                                [-121.0, 37.0],
                                [-121.0, 38.0],
                                [-122.0, 38.0],
                                [-122.0, 37.0],
                            ]
                        ],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "coverage.geojson"
            with open(geojson_path, "w") as f:
                json.dump(geojson_data, f)

            sampler = CoverageSampler(geojson_path)

            # Point outside coverage
            covered = sampler.check_coverage_at_point(39.0, -121.0)
            assert "POR" not in covered

    def test_multipolygon_support_idl_crossing(self):
        """Test multi-polygon support for IDL-crossing coverage."""
        # PORB split into two polygons (one on each side of IDL)
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "POR"},
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": [
                            # Western hemisphere part
                            [
                                [
                                    [170.0, -10.0],
                                    [180.0, -10.0],
                                    [180.0, 10.0],
                                    [170.0, 10.0],
                                    [170.0, -10.0],
                                ]
                            ],
                            # Eastern hemisphere part (crosses IDL)
                            [
                                [
                                    [-180.0, -10.0],
                                    [-170.0, -10.0],
                                    [-170.0, 10.0],
                                    [-180.0, 10.0],
                                    [-180.0, -10.0],
                                ]
                            ],
                        ],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "coverage.geojson"
            with open(geojson_path, "w") as f:
                json.dump(geojson_data, f)

            sampler = CoverageSampler(geojson_path)

            # Should have two rings for POR
            assert "POR" in sampler.satellite_polygons
            assert len(sampler.satellite_polygons["POR"]) == 2

            # Test point in western part
            covered_west = sampler.check_coverage_at_point(0.0, 175.0)
            assert "POR" in covered_west

            # Test point in eastern part (negative longitude)
            covered_east = sampler.check_coverage_at_point(0.0, -175.0)
            assert "POR" in covered_east

            # Test point outside
            covered_out = sampler.check_coverage_at_point(0.0, 90.0)
            assert "POR" not in covered_out

    def test_sample_route_coverage(self):
        """Test sampling route for coverage events."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "POR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-122.0, 37.0],
                                [-121.0, 37.0],
                                [-121.0, 38.0],
                                [-122.0, 38.0],
                                [-122.0, 37.0],
                            ]
                        ],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            geojson_path = Path(tmpdir) / "coverage.geojson"
            with open(geojson_path, "w") as f:
                json.dump(geojson_data, f)

            sampler = CoverageSampler(geojson_path)

            # Simulate route going into and out of coverage
            base_time = datetime.utcnow()
            waypoints = [
                (37.0, -123.0, base_time),  # Outside
                (37.5, -121.5, base_time + timedelta(minutes=1)),  # Inside
                (37.5, -121.5, base_time + timedelta(minutes=2)),  # Inside
                (37.0, -123.0, base_time + timedelta(minutes=3)),  # Outside
            ]

            events = sampler.sample_route_coverage(waypoints)

            # Should have entry and exit events
            assert len(events) >= 2

            # First event should be entry
            entry_events = [e for e in events if e.event_type == "entry"]
            exit_events = [e for e in events if e.event_type == "exit"]

            assert len(entry_events) > 0
            assert len(exit_events) > 0

    def test_save_and_load_coverage_events(self):
        """Test saving and loading coverage events."""
        events = [
            CoverageEvent(
                timestamp=datetime.utcnow(),
                event_type="entry",
                satellite_id="POR",
                latitude=30.0,
                longitude=120.0,
            ),
            CoverageEvent(
                timestamp=datetime.utcnow() + timedelta(hours=1),
                event_type="exit",
                satellite_id="POR",
                latitude=30.0,
                longitude=121.0,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "events.json"

            sampler = CoverageSampler()
            sampler.save_coverage_events(events, output_path)

            # Load and verify
            loaded_events = sampler.load_coverage_events(output_path)

            assert len(loaded_events) == 2
            assert loaded_events[0].event_type == "entry"
            assert loaded_events[1].event_type == "exit"

    def test_load_nonexistent_events_returns_empty(self):
        """Test that loading nonexistent events returns empty list."""
        sampler = CoverageSampler()
        events = sampler.load_coverage_events(Path("/nonexistent/events.json"))

        assert events == []

    def test_elevation_fallback_estimation(self):
        """Test math-based elevation fallback."""
        sampler = CoverageSampler()

        # Test elevation at different aircraft positions
        el1 = sampler.estimate_coverage_fallback(
            satellite_lon=0.0,
            aircraft_lat=0.0,
            aircraft_lon=0.0,
        )

        el2 = sampler.estimate_coverage_fallback(
            satellite_lon=0.0,
            aircraft_lat=30.0,
            aircraft_lon=0.0,
        )

        # Should be numeric values
        assert isinstance(el1, float)
        assert isinstance(el2, float)

        # Higher elevation when aircraft directly below satellite
        assert el1 > el2
