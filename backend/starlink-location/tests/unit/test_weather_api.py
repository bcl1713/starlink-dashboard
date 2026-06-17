"""Tests for weather radar API routes."""

from app.api import weather


def test_rainviewer_radar_tile_endpoint_redirects_to_latest_tile(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        weather.rainviewer_radar_service,
        "tile_url",
        lambda z, x, y: f"https://tilecache.rainviewer.com/radar/{z}/{x}/{y}.png",
    )

    response = client.get(
        "/api/weather/radar/rainviewer/3/4/5.png", follow_redirects=False
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "https://tilecache.rainviewer.com/radar/3/4/5.png"
    )
    assert response.headers["cache-control"] == "no-store"


def test_rainviewer_radar_tile_endpoint_allows_dashboard_refresh_token(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        weather.rainviewer_radar_service,
        "tile_url",
        lambda z, x, y: f"https://tilecache.rainviewer.com/radar/{z}/{x}/{y}.png",
    )

    response = client.get(
        "/api/weather/radar/rainviewer/3/4/5.png?refresh=202606171200",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "https://tilecache.rainviewer.com/radar/3/4/5.png"
    )
    assert response.headers["cache-control"] == "no-store"


def test_rainviewer_radar_tile_endpoint_returns_503_when_source_unavailable(
    client, monkeypatch
) -> None:
    def unavailable_tile_url(z: int, x: int, y: int) -> str:
        raise RuntimeError("RainViewer metadata unavailable")

    monkeypatch.setattr(
        weather.rainviewer_radar_service, "tile_url", unavailable_tile_url
    )

    response = client.get("/api/weather/radar/rainviewer/3/4/5.png")

    assert response.status_code == 503
    assert response.json() == {"detail": "RainViewer metadata unavailable"}
