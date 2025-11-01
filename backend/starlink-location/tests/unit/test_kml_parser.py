"""Unit tests for KML parser functionality."""

import tempfile
from pathlib import Path

import pytest

from app.models.route import ParsedRoute, RoutePoint
from app.services.kml_parser import KMLParseError, parse_kml_file, validate_kml_file

# Sample valid KML with a simple LineString
VALID_KML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Test Route</name>
    <description>A test route for unit testing</description>
    <Placemark>
      <name>Route Path</name>
      <LineString>
        <coordinates>
          -74.0060,40.7128,100
          -74.0070,40.7138,110
          -74.0080,40.7148,120
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""

# KML with folder structure
VALID_KML_FOLDER_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Folder Route</name>
    <Folder>
      <name>Waypoints</name>
      <Placemark>
        <LineString>
          <coordinates>
            0.0,0.0,0.0
            1.0,1.0,100.0
            2.0,2.0,200.0
          </coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""

# KML with route waypoints and segmented path
KML_WITH_WAYPOINTS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>KJFK-KBOS Test Route</name>
    <Placemark>
      <name>KJFK</name>
      <styleUrl>#departureIcon</styleUrl>
      <Point>
        <coordinates>-73.7781,40.6413,10</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Segment A</name>
      <LineString>
        <coordinates>
          -73.7781,40.6413,10
          -72.5000,41.0000,20
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Segment B</name>
      <LineString>
        <coordinates>
          -72.5000,41.0000,20
          -71.0050,42.3643,30
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>KBOS</name>
      <styleUrl>#arrivalIcon</styleUrl>
      <Point>
        <coordinates>-71.0050,42.3643,30</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""

# Invalid KML - no coordinates
INVALID_KML_NO_COORDS = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Empty Route</name>
    <Placemark>
      <name>Empty Path</name>
      <LineString>
        <coordinates>
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""

# Malformed KML
MALFORMED_KML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Malformed</name>
    <!-- Missing closing tag -->
</kml>"""


@pytest.fixture
def temp_kml_dir():
    """Create temporary directory for KML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_kml_file(temp_kml_dir):
    """Create a valid KML test file."""
    kml_file = temp_kml_dir / "test_route.kml"
    kml_file.write_text(VALID_KML_CONTENT)
    return kml_file


@pytest.fixture
def valid_kml_folder_file(temp_kml_dir):
    """Create a valid KML file with folder structure."""
    kml_file = temp_kml_dir / "folder_route.kml"
    kml_file.write_text(VALID_KML_FOLDER_CONTENT)
    return kml_file


@pytest.fixture
def invalid_kml_empty_file(temp_kml_dir):
    """Create an invalid KML file with no coordinates."""
    kml_file = temp_kml_dir / "empty_route.kml"
    kml_file.write_text(INVALID_KML_NO_COORDS)
    return kml_file


@pytest.fixture
def malformed_kml_file(temp_kml_dir):
    """Create a malformed KML file."""
    kml_file = temp_kml_dir / "malformed.kml"
    kml_file.write_text(MALFORMED_KML_CONTENT)
    return kml_file


@pytest.fixture
def kml_with_waypoints_file(temp_kml_dir):
    """Create a KML file containing waypoint placemarks."""
    kml_file = temp_kml_dir / "waypoints_route.kml"
    kml_file.write_text(KML_WITH_WAYPOINTS_CONTENT)
    return kml_file


class TestKMLParser:
    """Test suite for KML parser."""

    def test_parse_valid_kml(self, valid_kml_file):
        """Test parsing a valid KML file."""
        result = parse_kml_file(valid_kml_file)

        assert isinstance(result, ParsedRoute)
        assert result.metadata.name == "Test Route"
        assert result.metadata.description == "A test route for unit testing"
        assert len(result.points) == 3
        assert result.metadata.point_count == 3

    def test_parse_kml_points_structure(self, valid_kml_file):
        """Test that parsed points have correct structure."""
        result = parse_kml_file(valid_kml_file)

        points = result.points
        assert len(points) == 3

        # Check first point
        assert points[0].latitude == 40.7128
        assert points[0].longitude == -74.0060
        assert points[0].altitude == 100
        assert points[0].sequence == 0

        # Check second point
        assert points[1].latitude == 40.7138
        assert points[1].longitude == -74.0070
        assert points[1].altitude == 110
        assert points[1].sequence == 1

        # Check third point
        assert points[2].latitude == 40.7148
        assert points[2].longitude == -74.0080
        assert points[2].altitude == 120
        assert points[2].sequence == 2

    def test_parse_kml_metadata(self, valid_kml_file):
        """Test that metadata is correctly extracted."""
        result = parse_kml_file(valid_kml_file)

        assert result.metadata.name == "Test Route"
        assert result.metadata.description == "A test route for unit testing"
        assert result.metadata.file_path == str(valid_kml_file.absolute())
        assert result.metadata.point_count == 3
        assert result.metadata.imported_at is not None

    def test_parse_kml_with_folder(self, valid_kml_folder_file):
        """Test parsing KML with folder structure."""
        result = parse_kml_file(valid_kml_folder_file)

        assert result.metadata.name == "Folder Route"
        assert len(result.points) == 3

    def test_parse_invalid_kml_no_coords(self, invalid_kml_empty_file):
        """Test parsing KML with no coordinates."""
        with pytest.raises(KMLParseError, match="No coordinate data found"):
            parse_kml_file(invalid_kml_empty_file)

    def test_parse_malformed_kml(self, malformed_kml_file):
        """Test parsing malformed XML."""
        with pytest.raises(KMLParseError, match="Failed to parse KML"):
            parse_kml_file(malformed_kml_file)

    def test_parse_nonexistent_file(self, temp_kml_dir):
        """Test parsing non-existent file."""
        with pytest.raises(KMLParseError, match="KML file not found"):
            parse_kml_file(temp_kml_dir / "nonexistent.kml")

    def test_parse_non_kml_file(self, temp_kml_dir):
        """Test parsing non-KML file."""
        txt_file = temp_kml_dir / "test.txt"
        txt_file.write_text("not a KML file")

        with pytest.raises(KMLParseError, match="File is not a KML file"):
            parse_kml_file(txt_file)

    def test_get_bounds(self, valid_kml_file):
        """Test bounding box calculation."""
        result = parse_kml_file(valid_kml_file)
        bounds = result.get_bounds()

        assert bounds["min_lat"] == 40.7128
        assert bounds["max_lat"] == 40.7148
        assert bounds["min_lon"] == -74.0080
        assert bounds["max_lon"] == -74.0060

    def test_get_total_distance(self, valid_kml_file):
        """Test total distance calculation."""
        result = parse_kml_file(valid_kml_file)
        distance = result.get_total_distance()

        # Should be positive distance
        assert distance > 0
        # Distance between three nearby points should be reasonable (not huge)
        assert distance < 100000  # Less than 100km

    def test_validate_valid_kml(self, valid_kml_file):
        """Test validation of valid KML file."""
        is_valid, error = validate_kml_file(valid_kml_file)

        assert is_valid is True
        assert error is None

    def test_validate_invalid_kml(self, malformed_kml_file):
        """Test validation of invalid KML file."""
        is_valid, error = validate_kml_file(malformed_kml_file)

        assert is_valid is False
        assert error is not None
        assert "Failed to parse KML" in error

    def test_parse_kml_without_altitude(self, temp_kml_dir):
        """Test parsing KML coordinates without altitude."""
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            <name>No Altitude</name>
            <Placemark>
              <LineString>
                <coordinates>
                  -74.0060,40.7128
                  -74.0070,40.7138
                </coordinates>
              </LineString>
            </Placemark>
          </Document>
        </kml>"""

        kml_file = temp_kml_dir / "no_altitude.kml"
        kml_file.write_text(kml_content)

        result = parse_kml_file(kml_file)

        assert len(result.points) == 2
        assert result.points[0].altitude is None
        assert result.points[1].altitude is None

    def test_route_point_model_validation(self):
        """Test RoutePoint Pydantic validation."""
        # Valid point
        point = RoutePoint(latitude=40.0, longitude=-74.0, altitude=100, sequence=0)
        assert point.latitude == 40.0
        assert point.longitude == -74.0
        assert point.sequence == 0

    def test_parse_waypoints_from_kml(self, kml_with_waypoints_file):
        """Verify waypoint placemarks are extracted with roles and ordering."""
        result = parse_kml_file(kml_with_waypoints_file)

        assert result.metadata.name == "KJFK-KBOS Test Route"
        assert len(result.points) == 3  # start, mid, end deduplicated chain

        waypoints = result.waypoints
        assert len(waypoints) == 2

        departure = waypoints[0]
        arrival = waypoints[1]

        assert departure.name == "KJFK"
        assert departure.role == "departure"
        assert pytest.approx(departure.latitude, rel=1e-6) == 40.6413
        assert pytest.approx(departure.longitude, rel=1e-6) == -73.7781

        assert arrival.name == "KBOS"
        assert arrival.role == "arrival"
        assert pytest.approx(arrival.latitude, rel=1e-6) == 42.3643
        assert pytest.approx(arrival.longitude, rel=1e-6) == -71.005
