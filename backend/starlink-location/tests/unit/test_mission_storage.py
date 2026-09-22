"""Unit tests for scoped v2 mission storage."""

import json

import pytest

from app.mission import storage
from app.mission.models import Mission, MissionLeg, MissionLegTimeline, TransportConfig
from app.mission.storage import (
    delete_mission_timeline,
    get_active_leg_lock,
    get_leg_timeline_path,
    get_mission_file_path,
    get_mission_leg_file_path,
    list_mission_metadata_v2,
    load_mission_metadata_v2,
    load_mission_timeline,
    load_mission_v2,
    save_mission_timeline,
    save_mission_v2,
)


@pytest.fixture
def temp_missions_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def scoped_mission():
    return Mission(
        id="scoped",
        name="Scoped mission",
        legs=[
            MissionLeg(
                id="leg-1",
                name="Leg 1",
                route_id="route-1",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )


def test_save_mission_v2_persists_only_scoped_parent_and_leg_files(
    temp_missions_dir, scoped_mission
):
    save_mission_v2(scoped_mission)

    assert get_mission_file_path("scoped").is_file()
    assert get_mission_leg_file_path("scoped", "leg-1").is_file()
    assert not (temp_missions_dir / "scoped.json").exists()
    assert not (temp_missions_dir / "scoped.sha256").exists()


def test_load_mission_v2_round_trips_parent_and_legs(temp_missions_dir, scoped_mission):
    save_mission_v2(scoped_mission)

    loaded = load_mission_v2("scoped")

    assert loaded is not None
    assert loaded.id == "scoped"
    assert [leg.id for leg in loaded.legs] == ["leg-1"]


def test_v2_listing_ignores_flat_legacy_artifacts(temp_missions_dir, scoped_mission):
    legacy_artifacts = {
        "legacy.json": b'{"id": "legacy"}',
        "legacy.sha256": b"legacy-checksum",
        "legacy-leg.timeline.json": b'{"mission_leg_id": "legacy-leg"}',
    }
    for name, contents in legacy_artifacts.items():
        (temp_missions_dir / name).write_bytes(contents)
    save_mission_v2(scoped_mission)

    assert [item.id for item in list_mission_metadata_v2()] == ["scoped"]
    assert {
        name: (temp_missions_dir / name).read_bytes() for name in legacy_artifacts
    } == legacy_artifacts


def test_scoped_timeline_read_does_not_probe_or_migrate_flat_artifact(
    temp_missions_dir,
):
    timeline = MissionLegTimeline(mission_leg_id="legacy-leg")
    legacy_path = temp_missions_dir / "legacy-leg.timeline.json"
    legacy_bytes = json.dumps(timeline.model_dump(), default=str).encode()
    legacy_path.write_bytes(legacy_bytes)

    assert load_mission_timeline("legacy-leg", parent_mission_id="scoped") is None
    assert legacy_path.read_bytes() == legacy_bytes


def test_scoped_timeline_api_requires_a_parent_mission_id():
    with pytest.raises(TypeError):
        save_mission_timeline("leg-1", MissionLegTimeline(mission_leg_id="leg-1"))


def test_scoped_timeline_round_trip_and_deletion_do_not_touch_flat_artifact(
    temp_missions_dir,
):
    timeline = MissionLegTimeline(mission_leg_id="leg-1")
    flat_path = temp_missions_dir / "leg-1.timeline.json"
    flat_bytes = b"must-survive"
    flat_path.write_bytes(flat_bytes)

    save_mission_timeline("leg-1", timeline, parent_mission_id="scoped")
    assert load_mission_timeline("leg-1", parent_mission_id="scoped") == timeline
    assert get_leg_timeline_path("leg-1", "scoped").is_file()

    delete_mission_timeline("leg-1", parent_mission_id="scoped")
    assert not get_leg_timeline_path("leg-1", "scoped").exists()
    assert flat_path.read_bytes() == flat_bytes


def test_active_leg_lock_is_reused_for_the_scoped_repository(temp_missions_dir):
    assert get_active_leg_lock() is get_active_leg_lock()


def test_v2_metadata_listing_orders_persisted_timestamps(temp_missions_dir):
    def write_metadata(mission_id, **metadata):
        mission_dir = temp_missions_dir / mission_id
        mission_dir.mkdir()
        (mission_dir / "mission.json").write_text(
            json.dumps({"id": mission_id, "name": mission_id, **metadata})
        )

    write_metadata("newest", updated_at="2026-09-22T12:00:00Z")
    write_metadata("created-only", created_at="2026-09-21T12:00:00Z")
    write_metadata("invalid", updated_at="not-a-timestamp")
    write_metadata("missing")

    missions = list_mission_metadata_v2()

    assert [mission.id for mission in missions] == [
        "newest",
        "created-only",
        "invalid",
        "missing",
    ]


def test_v2_metadata_load_returns_leg_stubs_and_handles_invalid_data(temp_missions_dir):
    mission = Mission(
        id="metadata",
        name="Metadata mission",
        legs=[
            MissionLeg(
                id="leg-b",
                name="Leg B",
                route_id="route-b",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
            MissionLeg(
                id="leg-a",
                name="Leg A",
                route_id="route-a",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
        ],
        metadata={"customer": "Test Corp"},
    )
    save_mission_v2(mission)

    loaded = load_mission_metadata_v2("metadata")

    assert loaded is not None
    assert loaded.metadata == {"customer": "Test Corp"}
    assert [leg.id for leg in loaded.legs] == ["leg-a", "leg-b"]
    assert [leg.name for leg in loaded.legs] == ["leg-a", "leg-b"]

    invalid_dir = temp_missions_dir / "invalid"
    invalid_dir.mkdir()
    (invalid_dir / "mission.json").write_text("{ not valid JSON")
    assert load_mission_metadata_v2("invalid") is None
    assert [mission.id for mission in list_mission_metadata_v2()] == ["metadata"]


def test_v2_save_overwrites_metadata_and_prunes_stale_leg_files(temp_missions_dir):
    initial = Mission(
        id="overwrite",
        name="Initial name",
        legs=[
            MissionLeg(
                id="keep",
                name="Keep",
                route_id="route-keep",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
            MissionLeg(
                id="stale",
                name="Stale",
                route_id="route-stale",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
        ],
        metadata={"revision": 1},
    )
    save_mission_v2(initial)

    save_mission_timeline(
        "stale",
        MissionLegTimeline(mission_leg_id="stale"),
        parent_mission_id="overwrite",
    )
    updated = initial.model_copy(
        update={
            "name": "Updated name",
            "legs": [
                MissionLeg(
                    id="keep",
                    name="Keep",
                    route_id="route-keep",
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
            "metadata": {"revision": 2},
        }
    )
    save_mission_v2(updated)

    loaded = load_mission_v2("overwrite")
    assert loaded is not None
    assert loaded.name == "Updated name"
    assert loaded.metadata == {"revision": 2}
    assert [leg.id for leg in loaded.legs] == ["keep"]
    assert not get_mission_leg_file_path("overwrite", "stale").exists()
    assert get_leg_timeline_path("stale", "overwrite").is_file()


def test_v2_loads_exclude_scoped_timelines_from_full_and_metadata_legs(
    temp_missions_dir,
):
    mission = Mission(
        id="timeline-exclusion",
        name="Timeline exclusion",
        legs=[
            MissionLeg(
                id="leg-2",
                name="Leg 2",
                route_id="route-2",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
            MissionLeg(
                id="leg-1",
                name="Leg 1",
                route_id="route-1",
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            ),
        ],
    )
    save_mission_v2(mission)
    save_mission_timeline(
        "leg-1",
        MissionLegTimeline(mission_leg_id="leg-1"),
        parent_mission_id="timeline-exclusion",
    )

    full = load_mission_v2("timeline-exclusion")
    metadata = load_mission_metadata_v2("timeline-exclusion")

    assert full is not None
    assert metadata is not None
    assert [leg.id for leg in full.legs] == ["leg-1", "leg-2"]
    assert [leg.id for leg in metadata.legs] == ["leg-1", "leg-2"]
