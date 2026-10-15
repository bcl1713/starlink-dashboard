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


def pdf_bytes(two_legs=False):
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
    if two_legs:
        cells.extend(
            [
                (480, 55, "2"),
                (480, 70, "BBBB"),
                (480, 250, "01-Jan-2035"),
                (480, 303, "1100"),
                (465, 70, "CCCC"),
                (465, 250, "01-Jan-2035"),
                (465, 303, "1130"),
            ]
        )
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
        if value["state"] not in ["queued", "running"] and not (
            value["state"] == "ready" and value["stage"] == "applying_changes"
        ):
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


def test_revision_applies_automatically_and_records_history(importer):
    client, service = importer
    first = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "rev-original")
    wait(client, first.id)
    before = storage.load_mission_v2(first.mission_id)
    revision = service.start(
        pdf_bytes(), [("r.kml", kml_bytes())], "rev-next", first.mission_id
    )
    ready = wait(client, revision.id)
    assert ready["state"] == "committed", ready
    after = storage.load_mission_v2(first.mission_id)
    assert after.name == before.name and after.id == before.id
    assert after.legs[0].id == before.legs[0].id
    assert after.metadata["itinerary_import"]["revision"] == 2
    assert after.metadata["itinerary_import"]["history"]


def test_concurrent_takeoff_edit_is_preserved_during_automatic_revision(
    importer, monkeypatch
):
    from datetime import datetime, timezone

    from app.mission.itinerary_import import automatic_revision

    client, service = importer
    first = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "concurrent-original")
    wait(client, first.id)
    original = automatic_revision.stage_revision
    edited = False

    def edit_once(*args):
        nonlocal edited
        ready = original(*args)
        if not edited:
            current = storage.load_mission_v2(first.mission_id)
            current.legs[0].adjusted_departure_time = datetime(
                2035, 1, 1, 11, tzinfo=timezone.utc
            )
            storage.save_mission_v2(current)
            edited = True
        return ready

    monkeypatch.setattr(automatic_revision, "stage_revision", edit_once)
    revision = service.start(
        pdf_bytes(), [("r.kml", kml_bytes())], "concurrent-next", first.mission_id
    )
    assert wait(client, revision.id)["state"] == "committed"
    assert (
        storage.load_mission_v2(first.mission_id).legs[0].adjusted_departure_time.hour
        == 11
    )


def second_kml():
    return (
        kml_bytes()
        .replace(b"AAAA", b"CCCC")
        .replace(b"BBBB", b"AAAA")
        .replace(b"CCCC", b"BBBB")
        .replace(b"AAAA", b"CCCC")
        .replace(b"10:", b"11:")
    )


def test_partial_route_revision_reuses_other_legs(importer):
    client, service = importer
    first = service.start(
        pdf_bytes(True),
        [("one.kml", kml_bytes()), ("two.kml", second_kml())],
        "partial-original",
    )
    assert wait(client, first.id)["state"] == "committed"
    old = storage.load_mission_v2(first.mission_id)
    replacement = second_kml().replace(b"11:00:42", b"11:00:52")
    revision = service.start(
        pdf_bytes(True),
        [("changed.kml", replacement)],
        "partial-next",
        first.mission_id,
    )
    ready = wait(client, revision.id)
    assert ready["state"] == "committed", ready
    prepared = __import__("json").loads(
        (service.store.directory(revision.id) / "prepared.json").read_text()
    )
    retained_id = next(l.route_id for l in old.legs if l.name == "AAAA–BBBB")
    assert any(l["route_id"] == retained_id for l in prepared["mission"]["legs"])
    assert len(prepared["mission"]["legs"]) == 2


def test_resume_pending_conversion_uses_retained_pdf_and_attachments(importer):
    client, service = importer
    first = service.start(
        pdf_bytes(True),
        [("one.kml", kml_bytes()), ("two.kml", second_kml())],
        "pending-original",
    )
    assert wait(client, first.id)["state"] == "committed"
    current = storage.load_mission_v2(first.mission_id)
    provenance = current.metadata["itinerary_import"]
    pending_id = next(
        id
        for id, e in provenance["evidence"].items()
        if e["source_leg"]["ordinal"] == 2
    )
    evidence = provenance["evidence"].pop(pending_id)
    pending = evidence["source_leg"]
    pending["departure_time"] = "2035-01-01T11:01:00Z"
    attached = next(l for l in current.legs if l.id == pending_id)
    pending["route"] = {
        "route_id": attached.route_id,
        "source_id": attached.route_id,
        "content_hash": provenance["sources"]["routes"][attached.route_id],
        "filename": "saved-attachment.kml",
    }
    provenance["pending_legs"] = [pending]
    current.legs = [l for l in current.legs if l.id != pending_id]
    provenance["baseline"]["legs"] = [
        l for l in provenance["baseline"]["legs"] if l["id"] != pending_id
    ]
    storage.save_mission_v2(current)
    resumed = service.start(None, [], "pending-resume", current.id)
    ready = wait(client, resumed.id)
    assert ready["state"] == "committed", ready
    import json

    review = json.loads(
        (service.store.directory(resumed.id) / "review.json").read_bytes()
    )
    assert (
        review["itinerary"]["expected_legs"][1]["departure_time"]
        == "2035-01-01T11:01:00Z"
    )
    assert (
        len(
            json.loads(
                (service.store.directory(resumed.id) / "prepared.json").read_bytes()
            )["mission"]["legs"]
        )
        == 2
    )


def test_unconfigured_catalog_placeholder_does_not_block_usable_satellites(importer):
    from app.satellites import catalog

    _client, service = importer
    catalog.get_satellite_catalog().add_satellite(Satellite("X-placeholder", "X"))
    assert [s["id"] for s in service.environment()["satellites"]] == ["X-invented"]


def test_revision_reuses_current_route_after_ordinary_replacement(importer):
    from app.mission.itinerary_import.replacement import replace_route

    client, service = importer
    first = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "replace-original")
    assert wait(client, first.id)["state"] == "committed"
    mission = storage.load_mission_v2(first.mission_id)
    replaced = replace_route(
        service,
        mission.id,
        mission.legs[0].id,
        kml_bytes().replace(b"1,0,10000", b"1.01,0,10000"),
        "new.kml",
    )
    revision = service.start(pdf_bytes(), [], "replace-revision", mission.id)
    ready = wait(client, revision.id)
    assert ready["state"] == "committed", ready
    import json

    prepared = json.loads(
        (service.store.directory(revision.id) / "prepared.json").read_bytes()
    )
    assert prepared["mission"]["legs"][0]["route_id"] == replaced["leg"]["route_id"]
    from app.mission.planning.sources import source_closure

    committed = storage.load_mission_v2(mission.id)
    assert source_closure(committed, None)


def test_automatic_revision_prefers_uploaded_route_and_keeps_other_manual_edits(
    importer,
):
    from app.mission.itinerary_import.replacement import replace_route

    client, service = importer
    first = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "incoming-first")
    wait(client, first.id)
    current = storage.load_mission_v2(first.mission_id)
    replace_route(
        service,
        current.id,
        current.legs[0].id,
        kml_bytes().replace(b"1,0,10000", b"1.01,0,10000"),
        "manual.kml",
    )
    current = storage.load_mission_v2(current.id)
    manual_route = current.legs[0].route_id
    current.legs[0].notes = "Keep this note"
    storage.save_mission_v2(current)
    update = service.start(
        pdf_bytes(),
        [("new.kml", kml_bytes().replace(b"1,0,10000", b"1.02,0,10000"))],
        "incoming-next",
        current.id,
    )
    assert wait(client, update.id)["state"] == "committed"
    after = storage.load_mission_v2(current.id)
    assert after.legs[0].route_id != manual_route
    assert after.legs[0].notes == "Keep this note"
    assert after.metadata["itinerary_import"]["revision"] == 2


def test_automatic_revision_of_active_leg_can_retry_after_deactivation(importer):
    client, service = importer
    first = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "active-first")
    wait(client, first.id)
    current = storage.load_mission_v2(first.mission_id)
    current.legs[0].is_active = True
    storage.save_mission_v2(current)
    update = service.start(
        pdf_bytes(),
        [("new.kml", kml_bytes().replace(b"1,0,10000", b"1.02,0,10000"))],
        "active-next",
        current.id,
    )
    blocked = wait(client, update.id)
    assert blocked["state"] == "needs_input"
    assert blocked["issues"][0]["code"] == "active_leg_change"
    assert (
        storage.load_mission_v2(current.id).metadata["itinerary_import"]["revision"]
        == 1
    )
    current.legs[0].is_active = False
    storage.save_mission_v2(current)
    service.resolve(update.id, blocked["generation"], {})
    assert wait(client, update.id)["state"] == "committed"
