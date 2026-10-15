"""Existing itinerary plans become ordinary without recomputing accepted work."""

import pytest

from app.mission import storage
from app.mission.models import MissionLeg, TransportConfig
from tests.planning.test_store import (
    create,
    service,  # noqa: F401
)


def test_conversion_is_idempotent_preserves_active_choices_and_pending_sources(
    service,  # noqa: F811 - imported pytest fixture
):
    view, _ = create(service)
    mission, manifest = service.store._load(view.mission.id)
    installed = MissionLeg(
        id="installed",
        name="Reviewed",
        route_id="retained-route",
        is_active=True,
        transports=TransportConfig(initial_x_satellite_id="X-original"),
    )
    mission.legs = [installed]
    manifest.expected_legs[0].installed_leg_id = installed.id
    service.store.persist(mission, manifest)
    storage.save_mission_v2(mission)
    from app.mission.itinerary_import.migration import migrate_itinerary_mission

    first = migrate_itinerary_mission(mission.id, service.store)
    after = storage.load_mission_v2(mission.id)
    assert first.changed
    assert "itinerary_planning" not in after.metadata
    assert after.name == mission.name and after.id == mission.id
    assert after.legs[0].is_active
    assert after.legs[0].transports == installed.transports
    provenance = after.metadata["itinerary_import"]
    assert provenance["version"] == 1
    assert len(provenance["pending_legs"]) == 2
    assert provenance["source_records"]
    assert not migrate_itinerary_mission(mission.id, service.store).changed
    assert storage.load_mission_v2(mission.id) == after


def test_unknown_conversion_version_fails_without_writes(service):  # noqa: F811
    view, _ = create(service)
    before = storage.get_mission_file_path(view.mission.id).read_bytes()
    from app.mission.itinerary_import.migration import convert_mission

    mission = storage.load_mission_v2(view.mission.id)
    mission.metadata["itinerary_import"] = {"version": 999}
    with pytest.raises(ValueError, match="version"):
        convert_mission(mission)
    assert storage.get_mission_file_path(view.mission.id).read_bytes() == before


def test_ordinary_import_retains_itinerary_leg_order():
    from app.mission.models import Mission, MissionLeg

    mission = Mission(
        id="ordered",
        name="Ordered",
        legs=[
            MissionLeg(
                id="second",
                name="BBBB–CCCC",
                route_id="r2",
                transports={"initial_x_satellite_id": "X"},
            ),
            MissionLeg(
                id="first",
                name="AAAA–BBBB",
                route_id="r1",
                transports={"initial_x_satellite_id": "X"},
            ),
        ],
        metadata={
            "itinerary_import": {
                "version": 1,
                "evidence": {
                    "first": {"source_leg": {"ordinal": 1}},
                    "second": {"source_leg": {"ordinal": 2}},
                },
            }
        },
    )
    assert storage.mission_leg_order(mission).executable_ids == ("first", "second")

    from datetime import datetime, timezone

    evidence = mission.metadata["itinerary_import"]["evidence"]
    evidence["first"]["source_leg"]["departure_time"] = "2035-01-01T12:00:00Z"
    evidence["second"]["source_leg"]["departure_time"] = "2035-01-01T10:00:00Z"
    assert storage.mission_leg_order(mission).executable_ids == ("second", "first")
    mission.legs[1].adjusted_departure_time = datetime(
        2035, 1, 1, 9, tzinfo=timezone.utc
    )
    assert storage.mission_leg_order(mission).executable_ids == ("first", "second")
