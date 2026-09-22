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
