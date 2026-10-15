"""Unresolved imports expose enough evidence to correct only the affected field."""

from .test_creation_api import importer, kml_bytes, pdf_bytes, wait  # noqa: F401


def test_ambiguous_route_returns_names_and_source_legs_then_resumes(
    importer,  # noqa: F811 - imported pytest fixture
):
    client, service = importer
    op = service.start(
        pdf_bytes(),
        [("first.kml", kml_bytes()), ("second.kml", kml_bytes())],
        "ambiguous",
    )
    value = wait(client, op.id)
    assert value["state"] == "needs_input"
    details = value["details"]
    assert "itinerary" in details, (
        (service.store.directory(op.id) / "failure.txt").read_text()
        if (service.store.directory(op.id) / "failure.txt").exists()
        else value
    )
    assert details["itinerary"]["expected_legs"][0]["departure_airport"] == "AAAA"
    assert {r["name"] for r in details["routes"]} == {"first.kml", "second.kml"}
    leg = details["itinerary"]["expected_legs"][0]["id"]
    first, second = details["routes"]
    r = client.post(
        f"/api/v2/missions/itinerary-imports/{op.id}/resolutions",
        json={
            "generation": value["generation"],
            "choices": {"routes": {leg: first["id"]}, "ignored_routes": [second["id"]]},
        },
    )
    assert r.status_code == 202, r.text
    assert wait(client, op.id)["state"] == "committed"
