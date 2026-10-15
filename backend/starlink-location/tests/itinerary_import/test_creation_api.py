"""Actual PDF/KML ingestion creates ordinary inactive missions."""

import time
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.mission import storage
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


def pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=800, height=600)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    cells = [
        (570, 80, "Mission Itinerary"),
        (570, 280, "Mission: INVENTED Revision #: 1"),
        (545, 65, "Departure/Arrival Airport"),
        (545, 245, "Dep/Arr"),
        (545, 280, "Date"),
        (545, 302, r"\(UTC\)"),
        (545, 345, "Adj"),
        (520, 55, "1"),
        (520, 70, "AAAA"),
        (520, 250, "01-Jan-2035"),
        (520, 303, "1000"),
        (505, 70, "BBBB"),
        (505, 250, "01-Jan-2035"),
        (505, 303, "1030"),
    ]
    stream = DecodedStreamObject()
    stream.set_data(
        "\n".join(
            f"BT /F1 9 Tf 1 0 0 1 {x} {y} Tm ({text}) Tj ET" for y, x, text in cells
        ).encode()
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def kml_bytes():
    return b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>AAAA-BBBB</name>
    <Placemark><name>AAAA</name><description>Time Over Waypoint: 2035-01-01 10:00:42Z</description><Point><coordinates>0,0,10000</coordinates></Point></Placemark>
    <Placemark><name>BBBB</name><description>Time Over Waypoint: 2035-01-01 10:30:17Z</description><Point><coordinates>1,0,10000</coordinates></Point></Placemark>
    <Placemark><LineString><coordinates>0,0,10000 1,0,10000</coordinates></LineString></Placemark></Document></kml>"""


@pytest.fixture
def importer(tmp_path, monkeypatch):
    from app.mission.itinerary_import.routes import router
    from app.mission.itinerary_import.service import ImportService

    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("X-invented", "X", longitude=0))
    monkeypatch.setattr("app.satellites.catalog._catalog", catalog)
    service = ImportService(
        storage.MISSIONS_DIR,
        RouteManager(tmp_path / "routes"),
        POIManager(tmp_path / "pois.json"),
    )
    app = FastAPI()
    app.state.itinerary_import_service = service
    app.include_router(router)
    with TestClient(app) as client:
        yield client, service
    service.close()


def wait(client, id):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        result = client.get("/api/v2/missions/itinerary-imports/" + id)
        assert result.status_code == 200, result.text
        value = result.json()
        if value["state"] not in ["queued", "running"]:
            return value
        time.sleep(0.05)
    pytest.fail("Import did not terminate within 45 seconds")


def test_upload_generates_ordinary_mission_without_access_confirmation(importer):
    client, service = importer
    r = client.post(
        "/api/v2/missions/itinerary-imports",
        data={"idempotency_key": "same"},
        files=[
            ("pdf", ("itinerary.pdf", pdf_bytes(), "application/pdf")),
            ("kmls", ("route.kml", kml_bytes(), "application/xml")),
        ],
    )
    assert r.status_code == 202, r.text
    result = wait(client, r.json()["id"])
    assert result["state"] == "committed", result
    mission = storage.load_mission_v2(result["mission_id"])
    assert mission and len(mission.legs) == 1
    assert not mission.legs[0].is_active
    assert "itinerary_planning" not in mission.metadata
    assert mission.metadata["itinerary_import"]["version"] == 1
    assert mission.legs[0].transports.initial_x_satellite_id == "X-invented"
    assert storage.load_mission_timeline(
        mission.legs[0].id, parent_mission_id=mission.id
    )
    again = service.start(pdf_bytes(), [("route.kml", kml_bytes())], "same")
    assert again.id == result["id"]


def test_invalid_pdf_is_reported_without_partial_mission(importer):
    client, _ = importer
    r = client.post(
        "/api/v2/missions/itinerary-imports",
        data={"idempotency_key": "bad"},
        files=[("pdf", ("bad.pdf", b"not a pdf")), ("kmls", ("r.kml", kml_bytes()))],
    )
    result = wait(client, r.json()["id"])
    assert result["state"] == "needs_input"
    assert not storage.load_mission_v2(result["mission_id"])
    assert "Traceback" not in str(result)


def test_stale_resolutions_rejected(importer):
    client, _ = importer
    r = client.post(
        "/api/v2/missions/itinerary-imports",
        data={"idempotency_key": "bad"},
        files=[("pdf", ("bad.pdf", b"bad")), ("kmls", ("r.kml", kml_bytes()))],
    )
    result = wait(client, r.json()["id"])
    r = client.post(
        "/api/v2/missions/itinerary-imports/" + result["id"] + "/resolutions",
        json={"generation": 0, "choices": {}},
    )
    assert r.status_code == 409


def test_committed_route_retains_planning_profile_on_reload(importer):
    from app.mission.planning.sources import SourceStore

    client, service = importer
    op = service.start(pdf_bytes(), [("route.kml", kml_bytes())], "profile")
    value = wait(client, op.id)
    mission = storage.load_mission_v2(value["mission_id"])
    sources = SourceStore(storage.MISSIONS_DIR, service.route_manager.routes_dir)
    assert sources.resolve_profile(mission.legs[0].route_id) == "planning_v1"


def test_no_satellites_is_a_specific_correction(importer, monkeypatch):
    client, service = importer
    monkeypatch.setattr(
        service, "environment", lambda: {"satellites": [], "constraints": {}}
    )
    op = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "none")
    value = wait(client, op.id)
    assert value["state"] == "needs_input"
    assert any(i["code"] == "satellite_configuration" for i in value["issues"])


def test_cancelled_queued_operation_never_creates_mission(importer):
    _client, service = importer
    # Cancel a persisted operation before admitting it to the owned executor.
    op = service.store.create(pdf_bytes(), [("r.kml", kml_bytes())], "cancelled")
    value = service.cancel(op.id)
    service.run(op.id)
    assert value.state == "cancelled"
    assert storage.load_mission_v2(op.mission_id) is None
