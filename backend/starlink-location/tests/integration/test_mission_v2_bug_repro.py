from fastapi.testclient import TestClient
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.models.poi import POICreate
from uuid import uuid4


def test_delete_leg_scope_bug(client: TestClient):
    """
    Reproduction test for bug where deleting a leg deletes ALL mission POIs.
    """
    # 1. Create a mission with two legs
    mission_id = f"bug-repro-mission-{uuid4().hex[:8]}"
    leg1_id = f"leg-1-{uuid4().hex[:8]}"
    leg2_id = f"leg-2-{uuid4().hex[:8]}"

    route1_id = "route-1"
    route2_id = "route-2"

    leg1 = MissionLeg(
        id=leg1_id,
        name="Leg 1",
        route_id=route1_id,
        transports=TransportConfig(
            initial_x_satellite_id="X-1", initial_ka_satellite_ids=[]
        ),
        is_active=False,
    )

    leg2 = MissionLeg(
        id=leg2_id,
        name="Leg 2",
        route_id=route2_id,
        transports=TransportConfig(
            initial_x_satellite_id="X-1", initial_ka_satellite_ids=[]
        ),
        is_active=False,
    )

    mission = Mission(id=mission_id, name="Bug Repro Mission", legs=[leg1, leg2])

    # Create mission via API
    # Mocking build_mission_timeline to avoid errors if routes don't exist
    from unittest.mock import patch
    from app.mission.models import MissionLegTimeline
    from app.mission.timeline_service import TimelineSummary
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    timeline = MissionLegTimeline(mission_leg_id="test", segments=[])
    summary = TimelineSummary(
        mission_start=now,
        mission_end=now,
        degraded_seconds=0,
        critical_seconds=0,
        next_conflict_seconds=-1,
        transport_states={},
        sample_count=0,
        sample_interval_seconds=60,
        generation_runtime_ms=0,
    )

    with patch(
        "app.mission.routes_v2.build_mission_timeline", return_value=(timeline, summary)
    ):
        response = client.post("/api/v2/missions", json=mission.model_dump(mode="json"))
        assert response.status_code == 201

    # 2. Create POIs for each leg
    # Access poi_manager directly to verify internal state
    poi_manager = client.app.state.poi_manager

    # Create POI for Leg 1
    poi1 = POICreate(
        name="POI Leg 1",
        latitude=0,
        longitude=0,
        category="test",
        route_id=route1_id,
        mission_id=mission_id,
    )
    poi_manager.create_poi(poi1)

    # Create POI for Leg 2
    poi2 = POICreate(
        name="POI Leg 2",
        latitude=1,
        longitude=1,
        category="test",
        route_id=route2_id,
        mission_id=mission_id,
    )
    poi_manager.create_poi(poi2)

    # Verify POIs exist
    pois = poi_manager.list_pois(mission_id=mission_id)
    assert len(pois) == 2

    # 3. Delete Leg 1
    # We also mock build_mission_timeline here because delete might trigger things?
    # Actually delete_leg doesn't trigger timeline build, but let's be safe regarding other side effects.
    # However, delete_leg calls route_manager.get_route which might fail if route doesn't exist.
    # We mocked route_manager in conftest but it's empty.
    # Ideally we should put fake routes in route_manager if delete_leg checks for them.

    # Let's check delete_leg code again.
    # It calls route_manager.get_route(leg.route_id). If it fails, it logs error but continues.
    # So it should be fine even if routes are missing.

    response = client.delete(f"/api/v2/missions/{mission_id}/legs/{leg1_id}")
    assert response.status_code == 204

    # 4. Check if Leg 2's POI still exists
    remaining_pois = poi_manager.list_pois(mission_id=mission_id)

    # If bug exists, remaining_pois will be empty (or 0)
    # If bug is fixed, it should be 1 (POI for Leg 2)

    print(f"Remaining POIs: {[p.name for p in remaining_pois]}")

    assert (
        len(remaining_pois) == 1
    ), f"Expected 1 POI remaining, found {len(remaining_pois)}"
    assert remaining_pois[0].route_id == route2_id
