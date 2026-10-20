"""Ka evidence follows the evaluated sampler and distinguishes failed input."""

import json
from datetime import timedelta

import pytest

from app.mission import storage, timeline_service
from app.mission.models import KaOutage, MissionLeg, TransportConfig
from app.mission.pop_capabilities import saved_call_capabilities
from app.mission.pop_continuity import capabilities_from_timeline
from app.mission.timeline_preparation import prepare_mission_timeline
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.satellites.coverage import CoverageSampler
from app.services.route_manager import RouteManager
from tests.unit.test_mission_pop_forecast import BASE, route, sites


def footprints(left=-20, right=20):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"satellite_id": "Ka-test"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [left, -10],
                            [right, -10],
                            [right, 10],
                            [left, 10],
                            [left, -10],
                        ]
                    ],
                },
            }
        ],
    }


@pytest.fixture
def mission_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    default = tmp_path / "data/sat_coverage/commka.geojson"
    default.parent.mkdir(parents=True)
    default.write_text(json.dumps(footprints()))
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("r", route())
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="r",
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    catalog = SatelliteCatalog()
    catalog.add_satellite(Satellite("X-1", "X", longitude=180))
    return leg, manager, default, catalog


def prepare(sources, sampler):
    leg, manager, _, catalog = sources
    return prepare_mission_timeline(
        leg,
        manager,
        coverage_sampler=sampler,
        discover_coverage=False,
        satellite_catalog=catalog,
        pop_catalog=sites(("a", 0, -5), ("b", 0, 15)),
    )


@pytest.mark.parametrize(
    "source", ["custom", "custom_same", "stale_cache", "mutated_cache"]
)
def test_saved_reuse_rejects_different_or_unidentified_sampler(
    mission_sources, monkeypatch, source
):
    leg, _, default, catalog = mission_sources
    from app.mission import pop_capabilities

    monkeypatch.setattr(pop_capabilities, "get_satellite_catalog", lambda **kw: catalog)
    if source in ("custom", "custom_same"):
        sampler = CoverageSampler.from_geojson(
            footprints(40, 80) if source == "custom" else footprints()
        )
    else:
        sampler = CoverageSampler(default)
        monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", sampler)
        if source == "stale_cache":
            default.write_text(json.dumps(footprints(40, 80)))
        else:
            sampler.satellite_polygons = CoverageSampler.from_geojson(
                footprints(40, 80)
            ).satellite_polygons
    artifacts = prepare(mission_sources, sampler)
    storage.save_mission_timeline(leg.id, artifacts.timeline, "mission")
    assert saved_call_capabilities(leg, "mission", artifacts.route) is None


@pytest.mark.parametrize("kind", ["unloaded", "malformed", "missing"])
def test_failed_ka_input_is_unknown_and_cannot_fabricate_outage(mission_sources, kind):
    _, _, default, _ = mission_sources
    if kind == "malformed":
        default.write_text("not JSON")
        sampler = CoverageSampler(default)
    elif kind == "missing":
        sampler = CoverageSampler(default.with_name("missing.json"))
    else:
        sampler = CoverageSampler()
    result = prepare(mission_sources, sampler).timeline
    caps = capabilities_from_timeline(result)
    assert {c.ka for c in caps} == {"unknown"}
    assert result.call_continuity.pop_call_outage_seconds == 0
    assert result.call_continuity.planned_communications_outage_seconds == 0
    assert "unknown" in {i.classification for i in result.call_continuity.intervals}
    # Keep the legacy physical coverage-gap lane; unknown belongs to call evidence.
    assert any(s.ka_state == "degraded" for s in result.segments)


def test_valid_footprint_miss_is_confirmed_unavailable(mission_sources):
    result = prepare(
        mission_sources, CoverageSampler.from_geojson(footprints(40, 80))
    ).timeline
    assert {c.ka for c in capabilities_from_timeline(result)} == {"unavailable"}
    assert result.call_continuity.pop_call_outage_seconds == 600


def test_manual_ka_outage_remains_known_with_failed_coverage(mission_sources):
    leg, _, _, _ = mission_sources
    leg.transports.ka_outages = [
        KaOutage(
            id="manual-ka",
            start_time=BASE + timedelta(minutes=20),
            duration_seconds=600,
        )
    ]
    result = prepare(mission_sources, CoverageSampler()).timeline
    caps = capabilities_from_timeline(result)
    assert {
        c.ka
        for c in caps
        if c.start_utc >= BASE + timedelta(minutes=20)
        and c.end_utc <= BASE + timedelta(minutes=30)
    } == {"unavailable"}
    assert {c.ka for c in caps if c.end_utc <= BASE + timedelta(minutes=20)} == {
        "unknown"
    }
    assert result.call_continuity.pop_call_outage_seconds == 600


@pytest.mark.parametrize("source", ["default", "cache"])
def test_matching_identified_sampler_reuses_saved_capabilities(
    mission_sources, monkeypatch, source
):
    leg, manager, default, catalog = mission_sources
    from app.mission import pop_capabilities

    monkeypatch.setattr(pop_capabilities, "get_satellite_catalog", lambda **kw: catalog)
    sampler = None
    if source == "cache":
        sampler = CoverageSampler(default)
        monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", sampler)
    artifacts = prepare_mission_timeline(
        leg,
        manager,
        coverage_sampler=sampler,
        discover_coverage=True,
        satellite_catalog=catalog,
        pop_catalog=sites(("a", 0, -5), ("b", 0, 15)),
    )
    storage.save_mission_timeline(leg.id, artifacts.timeline, "mission")
    assert saved_call_capabilities(leg, "mission", artifacts.route) is not None


@pytest.mark.parametrize("source", ["same_stat_disk", "cache"])
def test_saved_reuse_rejects_content_change_even_without_default_stat_change(
    mission_sources, monkeypatch, source
):
    import os

    leg, manager, default, catalog = mission_sources
    from app.mission import pop_capabilities

    monkeypatch.setattr(pop_capabilities, "get_satellite_catalog", lambda **kw: catalog)
    default.write_text(json.dumps(footprints(20, 40)))
    artifacts = prepare_mission_timeline(
        leg,
        manager,
        discover_coverage=True,
        satellite_catalog=catalog,
        pop_catalog=sites(("a", 0, -5), ("b", 0, 15)),
    )
    storage.save_mission_timeline(leg.id, artifacts.timeline, "mission")
    assert saved_call_capabilities(leg, "mission", artifacts.route) is not None
    original = default.stat()
    if source == "cache":
        monkeypatch.setattr(
            timeline_service,
            "_COVERAGE_SAMPLER",
            CoverageSampler.from_geojson(footprints(60, 80)),
        )
    else:
        default.write_text(json.dumps(footprints(60, 80)))
        os.utime(default, ns=(original.st_atime_ns, original.st_mtime_ns))
        assert (default.stat().st_mtime_ns, default.stat().st_size) == (
            original.st_mtime_ns,
            original.st_size,
        )
    assert saved_call_capabilities(leg, "mission", artifacts.route) is None


@pytest.mark.parametrize("manual", [False, True])
def test_failed_policy_coverage_retains_only_explicit_manual_ka_evidence(manual):
    from app.mission.pop_continuity import attach_call_continuity
    from tests.unit.test_mission_pop_continuity import timeline
    from tests.unit.test_pop_continuity import END, START

    result = timeline(raw=("x_elevation",), physical="degraded", x="degraded")
    result.statistics["_call_capability_evidence"] = {
        "ka": False,
        "ka_manual_outages": (
            [{"start_utc": START.isoformat(), "end_utc": END.isoformat()}]
            if manual
            else []
        ),
    }
    physical = result.segments[0].model_dump()
    attach_call_continuity(result)
    assert {c.ka for c in capabilities_from_timeline(result)} == (
        {"unavailable"} if manual else {"unknown"}
    )
    assert result.call_continuity.pop_call_outage_seconds == (600 if manual else 0)
    assert result.segments[0].model_dump() == physical
