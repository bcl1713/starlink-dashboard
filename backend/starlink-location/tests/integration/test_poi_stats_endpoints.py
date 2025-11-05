"""Integration tests for POI stats endpoints used by Grafana."""


def test_next_destination_stats_returns_eta_metadata(test_client):
    response = test_client.get("/api/pois/stats/next-destination")
    assert response.status_code == 200

    payload = response.json()
    assert "name" in payload
    assert "eta_type" in payload
    assert "flight_phase" in payload
    assert "eta_seconds" in payload
    assert payload["eta_type"] in {"anticipated", "estimated"}


def test_next_eta_stats_returns_eta_metadata(test_client):
    response = test_client.get("/api/pois/stats/next-eta")
    assert response.status_code == 200

    payload = response.json()
    assert "eta_seconds" in payload
    assert "eta_type" in payload
    assert "flight_phase" in payload
    assert payload["eta_type"] in {"anticipated", "estimated"}
