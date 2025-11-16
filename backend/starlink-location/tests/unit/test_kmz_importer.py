import xml.etree.ElementTree as ET

from app.satellites import kmz_importer

SAMPLE_KML = """
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>BOEING_HCX PORB</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              0,0 1,0 1,1 0,1 0,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""


def test_extract_polygon_accepts_prefixed_hcx_names():
    root = ET.fromstring(SAMPLE_KML)
    coords = kmz_importer.extract_polygon_from_kml(root, "PORB")
    assert coords is not None
    assert len(coords) == 5


def test_extract_polygon_non_matching_name_returns_none():
    root = ET.fromstring(SAMPLE_KML)
    coords = kmz_importer.extract_polygon_from_kml(root, "AOR")
    assert coords is None
