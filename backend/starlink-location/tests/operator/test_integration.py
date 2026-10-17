"""Synthetic #348/#349 integration; operational format is not field evidence."""

import hashlib
import io
import json
import zipfile
from uuid import uuid4

import pytest

from app.mission import storage
from app.mission.pop_capabilities import capture_call_capabilities
from app.mission.pop_continuity import (
    attach_call_continuity,
    capabilities_from_timeline,
)
from app.mission.pop_status import PopStatusService
from app.operator.models import RecordFilter
from app.operator.projections import capture_projection
from app.operator.runtime import OperatorRuntime
from app.operator.settings import OperatorSettings
from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive.package import build_telemetry_package
from tests.operator.fixtures import ScenarioClock, make_demo, pop_inputs, seed_demo


def test_real_pop_and_flight_boundaries(tmp_path, monkeypatch):
    clock = ScenarioClock()
    seeded = seed_demo(tmp_path, clock=clock, mode="simulation")
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    demo = make_demo(clock)
    runtime = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=tmp_path / "operator",
            source_mode="simulation",
            simulation_run_id=demo["run_id"],
        ),
        clock=clock,
    )
    try:
        service = runtime.service
        for fallback, expected in [(None, 600), ("Ka", 0), ("X", 0)]:
            inputs = pop_inputs(clock, fallback=fallback)
            timeline = inputs.pop("timeline")
            sample = inputs.pop("telemetry")
            observation = inputs.pop("observation")
            assert capabilities_from_timeline(timeline)[0].starshield == "available"
            attach_call_continuity(timeline)
            assert timeline.call_continuity.pop_call_outage_seconds == expected
            caps = capture_call_capabilities(
                timeline, inputs["route"], inputs["projector"]
            )
            snapshot = PopStatusService(
                observation_provider=lambda *args, observation=observation: observation
            ).snapshot(sample, call_capabilities=caps, **inputs)
            assert snapshot["pop_observation"]["status"] == "unknown"
            assert "observation_unknown" in {
                a["kind"] for a in snapshot["pop_advisories"]
            }
            assert snapshot["call_continuity"]["pop_call_outage_seconds"] == expected
        # Unknown timing is unavailable forecast evidence, never a transport down flag.
        stale = pop_inputs(clock)
        stale.pop("timeline")
        sample = stale.pop("telemetry")
        observation = stale.pop("observation")
        stale.pop("projector")
        sample.position.observed_at = None
        unknown = PopStatusService(
            observation_provider=lambda *args, observation=observation: observation
        ).snapshot(sample, **stale)
        assert unknown["pop_forecast"]["status"] == "unavailable"
        command = demo["commands"][0].model_copy(deep=True)
        command.payload.note = json.dumps(
            {
                "synthetic": True,
                "decision": "Retain planned fallback; no routing action",
                "source_ref": {
                    "producer_id": "mission_pop_forecast",
                    "revision": timeline.pop_forecast.revision,
                },
            }
        )
        decision = service.execute(
            command, key=str(uuid4()), epoch=seeded["epoch"]
        ).saved_records[0]
        assert json.loads(service.get(decision.record_id).payload.note)["source_ref"][
            "revision"
        ]
        assert decision.provenance.kind == "operator_reported"
        assert decision.provenance.source_mode == "simulation"
    finally:
        runtime.close()


def test_synthetic_operational_format_archive_is_unchanged(tmp_path, monkeypatch):
    """Fresh synthetic live-format inputs exercise the existing operational builder."""
    from scenario import SyntheticRawReader, flight_observations

    clock = ScenarioClock()
    demo = make_demo(clock)
    seeded = seed_demo(tmp_path, clock=clock, mode="simulation")
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    operator = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=tmp_path / "operator",
            source_mode="simulation",
            simulation_run_id=demo["run_id"],
        ),
        clock=clock,
    )
    flight = FlightEventRuntime(tmp_path / "synthetic-operational-format")
    try:
        saved_before_flight = {
            mission.id: operator.service.list(RecordFilter(mission_id=mission.id)).items
            for mission in demo["missions"]
        }
        mission = demo["missions"][0].id
        legs = [leg.id for leg in demo["missions"][0].legs]
        for index, leg in enumerate(legs):
            for observation in flight_observations(
                clock, mission, leg, offset=index * 3000
            ):
                flight.accept(observation)
            assert [e.kind for e in flight.events.events(mission, leg)] == [
                "off_blocks",
                "takeoff",
                "landed",
                "on_blocks",
            ]
        clock.advance(6000)
        flight.capture.recover(clock.now())
        reader = SyntheticRawReader()
        for _ in range(500):
            clock.advance(300)
            flight.capture.backfill_one(reader, clock.now())
            flight.capture.recover(clock.now())
        captures = [flight.archive.capture(mission, leg) for leg in legs]
        assert all(c["state"] == "sealed" for c in captures)
        assert all(c["gaps"] and not c["complete"] for c in captures)
        with pytest.raises(ValueError, match="incomplete"):
            build_telemetry_package(mission, captures, allow_partial=False)
        baseline = build_telemetry_package(mission, captures, allow_partial=True)
        for mission_id, rows in saved_before_flight.items():
            assert (
                operator.service.list(RecordFilter(mission_id=mission_id)).items == rows
            )
        projection = capture_projection(operator.service.store, mission_id=mission)
        assert set(projection.files) == {
            "operations/current.json",
            "operations/activity.jsonl",
        }
        before = operator.service.list(RecordFilter(mission_id=mission)).items
        extra = demo["commands"][0].model_copy(deep=True)
        extra.payload.note = (
            "Synthetic decision after second leg; association remains explicit"
        )
        operator.service.execute(extra, key=str(uuid4()), epoch=seeded["epoch"])
        assert [operator.service.get(row.record_id) for row in before] == before
        conference = next(row for row in before if row.record_type == "conference")
        assert conference.time.end_state == "ongoing"
        assert all(row.leg_id != legs[1] for row in before if row.scope == "leg")
        flight.close()
        flight = FlightEventRuntime(tmp_path / "synthetic-operational-format")
        flight.capture.recover(clock.now())
        after = [flight.archive.capture(mission, leg) for leg in legs]
        assert after == captures  # Includes revision, identity, gaps and event IDs.
        assert build_telemetry_package(mission, after, allow_partial=True) == baseline
        with zipfile.ZipFile(io.BytesIO(baseline)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["partial"]
            assert not any(
                name.startswith("operations/") for name in archive.namelist()
            )
            for leg in manifest["legs"]:
                for filename, digest in leg["checksum"].items():
                    assert (
                        hashlib.sha256(
                            archive.read(leg["path"] + "/" + filename)
                        ).hexdigest()
                        == digest
                    )
                assert b"synthetic" in archive.read(leg["path"] + "/observations.csv")
        simulated = [dict(c, source_mode="simulation") for c in captures]
        with pytest.raises(ValueError, match="simulation"):
            build_telemetry_package(mission, simulated, allow_partial=True)
    finally:
        flight.close()
        operator.close()
