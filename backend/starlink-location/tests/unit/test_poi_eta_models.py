"""Unit tests for POI ETA response models."""

from datetime import datetime, timezone

from app.models.poi import POIETAListResponse, POIWithETA


def test_poi_with_eta_defaults():
    """Ensure POIWithETA populates defaults for optional metadata."""
    poi = POIWithETA(
        poi_id="poi-1",
        name="POI 1",
        latitude=40.0,
        longitude=-74.0,
        active=True,
        eta_seconds=120.0,
        distance_meters=500.0,
    )

    assert poi.eta_type == "estimated"
    assert poi.is_pre_departure is False
    assert poi.flight_phase is None
    assert poi.category is None
    assert poi.route_aware_status is None

    serialized = poi.model_dump(mode="json")
    assert serialized["eta_type"] == "estimated"
    assert serialized["distance_meters"] == 500.0
    assert "route_aware_status" in serialized


def test_poi_with_eta_with_route_metadata():
    """POIWithETA should accept route-aware projection properties."""
    poi = POIWithETA(
        poi_id="poi-2",
        name="Projected POI",
        latitude=41.0,
        longitude=-73.0,
        active=True,
        category="airport",
        eta_seconds=450.0,
        eta_type="anticipated",
        is_pre_departure=True,
        flight_phase="pre_departure",
        distance_meters=10000.0,
        bearing_degrees=180.0,
        is_on_active_route=True,
        projected_latitude=40.9,
        projected_longitude=-73.1,
        projected_waypoint_index=5,
        projected_route_progress=45.0,
        route_aware_status="ahead_on_route",
    )

    assert poi.category == "airport"
    assert poi.eta_type == "anticipated"
    assert poi.is_on_active_route is True
    assert poi.projected_route_progress == 45.0
    assert poi.route_aware_status == "ahead_on_route"


def test_poi_eta_list_response_defaults():
    """POIETAListResponse should provide sane defaults."""
    before = datetime.now(timezone.utc)
    response = POIETAListResponse()
    after = datetime.now(timezone.utc)

    assert response.pois == []
    assert response.total == 0
    assert before <= response.timestamp <= after
