"""Capability extraction preserves independent blocks and physical timeline states."""

import pytest

from app.mission.models import MissionLegTimeline, TimelineSegment
from app.mission.pop_continuity import (
    attach_call_continuity,
    capabilities_from_timeline,
)
from tests.unit.test_pop_continuity import CENTER, END, START, forecast


def timeline(
    *, raw=(), physical="available", policy="available", metadata=None, x="available"
):
    interval = {
        "start_time": START.isoformat(),
        "end_time": END.isoformat(),
        "physical_x_state": physical,
        "physical_ka_state": "offline",
        "physical_ku_state": "available",
        "policy_x_state": policy,
        "policy_ka_state": "offline",
        "policy_ku_state": "available",
        "raw_constraints": list(raw),
        "physical_reasons": [],
        "policy_reasons": [],
    }
    return MissionLegTimeline(
        mission_leg_id="leg",
        pop_forecast=forecast(CENTER),
        segments=[
            TimelineSegment(
                id="source",
                start_time=START,
                end_time=END,
                status="critical",
                x_state=x,
                ka_state="offline",
                ku_state="available",
                metadata=(
                    metadata
                    if metadata is not None
                    else {
                        "planning_policy": "prefer_starshield_v1",
                        "planning_interval": interval,
                        "transport_constraints": {"X": list(raw)},
                    }
                ),
            )
        ],
        statistics={"critical_seconds": 1200, "outage_seconds": 1200},
    )


@pytest.mark.parametrize("hard", ["x_ar_cone", "x_elevation", "manual:1", "swap:1"])
def test_concurrency_plus_independent_block_is_not_fallback(hard):
    result = timeline(
        raw=("x_aft_cone", hard), physical="degraded", policy="offline", x="offline"
    )
    before = result.model_dump()
    caps = capabilities_from_timeline(result)
    assert caps[0].x == "unavailable"
    assert caps[0].x_concurrency_only is False
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 600
    assert result.segments[0].model_dump() == before["segments"][0]
    assert result.statistics["critical_seconds"] == 1200
    assert result.statistics["outage_seconds"] == 1200


def test_policy_concurrency_uses_physical_capability():
    result = timeline(raw=("x_aft_cone",), policy="offline", x="offline")
    caps = capabilities_from_timeline(result)
    assert caps[0].x == "unavailable"
    assert caps[0].x_concurrency_only is True
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 0
    assert "x_fallback" in {i.classification for i in result.call_continuity.intervals}


@pytest.mark.parametrize(
    "metadata",
    [
        {"transport_constraints": {"X": ["x_aft_cone", "x_ar_cone"]}},
        {"transport_constraints": {"X": ["x_aft_cone", "x_elevation"]}},
        {"transport_constraints": {"X": ["x_aft_cone", "swap:1"]}},
    ],
)
def test_legacy_independent_constraints_survive_prominent_conflict_reason(metadata):
    result = timeline(metadata=metadata, x="degraded")
    result.segments[0].reasons = ["X-Ku Conflict plus X Band / AAR conflict"]
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 600


def test_legacy_reason_string_cannot_prove_recoverable_x():
    result = timeline(metadata={}, x="offline")
    result.segments[0].reasons = ["X-Ku Conflict"]
    assert capabilities_from_timeline(result)[0].x == "unknown"
    attach_call_continuity(result)
    assert "unknown" in {i.classification for i in result.call_continuity.intervals}


def test_missing_policy_prerequisite_is_unknown():
    result = timeline(raw=("x_aft_cone",), policy="offline", x="offline")
    del result.segments[0].metadata["planning_interval"]["physical_x_state"]
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 0
    assert "unknown" in {i.classification for i in result.call_continuity.intervals}


def test_absent_forecast_is_unavailable_and_old_payload_defaults():
    result = timeline()
    result.pop_forecast = None
    attach_call_continuity(result)
    assert result.call_continuity is None
    assert MissionLegTimeline(mission_leg_id="old").call_continuity is None


def test_all_transports_blocked_is_existing_outage_even_when_pop_unavailable():
    result = timeline(raw=("x_elevation",), physical="degraded", x="degraded")
    result.segments[0].metadata["planning_interval"]["physical_ku_state"] = "offline"
    result.pop_forecast = forecast(status="unavailable")
    attach_call_continuity(result)
    assert result.call_continuity.planned_communications_outage_seconds == 1200
    assert result.call_continuity.pop_call_outage_seconds == 0


def test_legacy_typed_concurrency_only_can_be_fallback():
    result = timeline(
        metadata={"transport_constraints": {"X": ["x_aft_cone"]}}, x="degraded"
    )
    result.segments[0].reasons = ["X-Ku Conflict"]
    attach_call_continuity(result)
    assert "x_fallback" in {i.classification for i in result.call_continuity.intervals}


def test_legacy_combined_reason_retains_independent_block_with_typed_cone():
    result = timeline(
        metadata={"transport_constraints": {"X": ["x_aft_cone"]}}, x="degraded"
    )
    result.segments[0].reasons = ["X-Ku Conflict plus X Band / AAR conflict"]
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 600


def test_independent_legacy_offline_is_existing_outage():
    result = timeline(
        metadata={"transport_constraints": {"X": ["manual:1"]}}, x="offline"
    )
    result.segments[0].ku_state = "offline"
    attach_call_continuity(result)
    assert result.call_continuity.planned_communications_outage_seconds == 1200


def test_prepared_timeline_publishes_totals_and_capability_input_identity(tmp_path):
    from app.mission.models import MissionLeg, TransportConfig
    from app.mission.pop_capabilities import capability_input_revision
    from app.mission.timeline_preparation import prepare_mission_timeline
    from app.services.route_manager import RouteManager
    from tests.unit.test_mission_pop_forecast import route

    r = route()
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", r)
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    artifacts = prepare_mission_timeline(leg, manager, discover_coverage=False)
    result = artifacts.timeline
    assert result.call_continuity is not None
    assert result.call_capability_revision == capability_input_revision(
        leg,
        artifacts.route,
        ka_snapshot=result.statistics["_call_capability_evidence"]["ka_snapshot"],
    )
    assert (
        result.statistics["pop_call_outage_seconds"]
        == result.call_continuity.pop_call_outage_seconds
    )
    leg.transports.starshield_enabled = False
    assert result.call_capability_revision != capability_input_revision(
        leg,
        artifacts.route,
        ka_snapshot=result.statistics["_call_capability_evidence"]["ka_snapshot"],
    )


def test_missing_captured_coverage_and_geometry_are_unknown():
    result = timeline(metadata={}, x="available")
    result.segments[0].ka_state = "available"
    result.statistics["_call_capability_evidence"] = {
        "ka": False,
        "x": False,
        "starshield_enabled": True,
    }
    caps = capabilities_from_timeline(result)
    assert caps[0].ka == caps[0].x == "unknown"


def test_independent_legacy_all_offline_outage_survives():
    result = timeline(metadata={}, x="offline")
    result.segments[0].ku_state = "offline"
    attach_call_continuity(result)
    assert result.call_continuity.planned_communications_outage_seconds == 1200


def test_known_x_physical_availability_survives_unrelated_safety_advice():
    result = timeline(metadata={}, x="available")
    result.segments[0].reasons = ["Safety-of-flight (AAR)"]
    assert capabilities_from_timeline(result)[0].x == "available"


def test_emitted_legacy_concurrency_reason_requires_typed_evidence():
    result = timeline(
        metadata={"transport_constraints": {"X": ["x_aft_cone"]}}, x="degraded"
    )
    result.segments[0].reasons = ["X-Ku Conflict az=180° el=40°"]
    assert capabilities_from_timeline(result)[0].x_concurrency_only is True


def test_policy_retains_additional_raw_constraint_evidence():
    result = timeline(raw=("x_aft_cone",), policy="offline", x="offline")
    result.segments[0].metadata["transport_constraints"]["X"].append("x_ar_cone")
    attach_call_continuity(result)
    assert result.call_continuity.pop_call_outage_seconds == 600


def test_policy_stale_interval_cannot_supply_known_ka():
    result = timeline()
    result.segments[0].metadata["planning_interval"]["start_time"] = CENTER.isoformat()
    result.segments[0].metadata["planning_interval"]["physical_ka_state"] = "available"
    caps = capabilities_from_timeline(result)
    assert caps[0].ka == caps[0].starshield == "unknown"


def test_removing_forecast_clears_old_projection_totals():
    result = timeline(raw=("x_elevation",), physical="degraded", x="degraded")
    attach_call_continuity(result)
    assert result.statistics["pop_call_outage_seconds"] == 600
    result.pop_forecast = None
    attach_call_continuity(result)
    assert result.call_continuity is None
    assert "pop_call_outage_seconds" not in result.statistics
