"""Production export baselines with explicitly synthetic operational-format input."""

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.mission.package.__main__ import generate_mission_combined_csv
from app.operator.models import CreateRecord, RecordFilter
from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.telemetry_archive.package import build_telemetry_package
from scenario import (
    ScenarioClock,
    SyntheticRawReader,
    flight_observations,
    make_demo,
    pop_inputs,
)
from store_probe import command, open_service


def digest(value):
    return hashlib.sha256(value).hexdigest()


def probe(root):
    clock = ScenarioClock()
    service = open_service(root)
    demo = make_demo(clock)
    mission = demo["missions"][0]
    timeline = pop_inputs(clock)["timeline"]
    for leg in mission.legs:
        storage.save_mission_timeline(leg.id, timeline, parent_mission_id=mission.id)
    # Only the generated-at CSV header is excluded from the semantic comparison.
    before_csv = generate_mission_combined_csv(mission).splitlines()[1:]
    base = command().model_dump(mode="json")
    base.update(scope="mission", leg_id=None, time={})
    conference_command = CreateRecord.model_validate(
        dict(
            base,
            record_type="conference",
            payload={
                "entry_type": "conference",
                "title": "Synthetic lifecycle conference",
                "status": "established",
            },
        )
    )
    epoch = str(service.store.health().api_epoch)
    conference = service.execute(
        conference_command, key=str(uuid4()), epoch=epoch
    ).saved_records[0]
    for _ in range(2):
        participant = CreateRecord.model_validate(
            dict(
                base,
                record_type="participation",
                payload={
                    "entry_type": "participation",
                    "title": "Synthetic lifecycle customer",
                    "state": "connected",
                    "conference_id": str(conference.record_id),
                },
            )
        )
        service.execute(participant, key=str(uuid4()), epoch=epoch)

    for payload in (
        {
            "entry_type": "issue",
            "title": "Synthetic spanning-leg problem",
            "status": "monitoring",
            "mitigation": "workaround",
        },
        {
            "entry_type": "capability_assessment",
            "title": "Synthetic secure voice",
            "functional_status": "functional",
            "redundancy_status": "unavailable",
        },
    ):
        service.execute(
            CreateRecord.model_validate(
                dict(
                    base,
                    record_type=(
                        "issue" if payload["entry_type"] == "issue" else "journal_entry"
                    ),
                    payload=payload,
                )
            ),
            key=str(uuid4()),
            epoch=epoch,
        )

    def issue_records():
        return {
            str(r.record_id): r.model_dump(mode="json")
            for r in service.list(RecordFilter(mission_id=mission.id)).items
            if r.payload.entry_type in ("issue", "capability_assessment")
        }

    before_issues = issue_records()

    def conference_records():
        return {
            str(r.record_id): r.model_dump(mode="json")
            for r in service.list(RecordFilter(mission_id=mission.id)).items
            if r.record_type in ("conference", "participation")
        }

    before_conferences = conference_records()
    flight = FlightEventRuntime(root / "synthetic-operational-format")
    try:
        for index, leg in enumerate(mission.legs):
            for observation in flight_observations(
                clock, mission.id, leg.id, offset=index * 3000
            ):
                flight.accept(observation)
        clock.advance(6000)
        flight.capture.recover(clock.now())
        reader = SyntheticRawReader()
        for _ in range(500):
            clock.advance(300)
            flight.capture.backfill_one(reader, clock.now())
            flight.capture.recover(clock.now())
        captures = [flight.archive.capture(mission.id, leg.id) for leg in mission.legs]
        assert all(
            c["state"] == "sealed" and c["gaps"] and not c["complete"] for c in captures
        )
        try:
            build_telemetry_package(mission.id, captures, allow_partial=False)
            raise AssertionError("Incomplete capture silently exported as complete")
        except ValueError as error:
            assert "incomplete" in str(error)
        baseline = build_telemetry_package(mission.id, captures, allow_partial=True)
        service.execute(
            command(), key=str(uuid4()), epoch=str(service.store.health().api_epoch)
        )
        after_csv = generate_mission_combined_csv(mission).splitlines()[1:]
        assert before_csv == after_csv and len(after_csv) > 5
        flight.close()
        flight = FlightEventRuntime(root / "synthetic-operational-format")
        after = [flight.archive.capture(mission.id, leg.id) for leg in mission.legs]
        assert after == captures
        exported = build_telemetry_package(mission.id, after, allow_partial=True)
        assert exported == baseline
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert not any(n.startswith("operations/") for n in archive.namelist())
            for leg in manifest["legs"]:
                for name, checksum in leg["checksum"].items():
                    assert digest(archive.read(leg["path"] + "/" + name)) == checksum
                assert b"synthetic" in archive.read(leg["path"] + "/observations.csv")
        try:
            build_telemetry_package(
                mission.id,
                [dict(c, source_mode="simulation") for c in captures],
                allow_partial=True,
            )
            raise AssertionError("Simulation export accepted by operational builder")
        except ValueError as error:
            assert "simulation" in str(error)
        assert conference_records() == before_conferences
        assert issue_records() == before_issues
        return {
            "conferenceLifecycleUnchanged": True,
            "issueCapabilityLifecycleUnchanged": True,
            "fixture": "separately generated synthetic operational-format input; never relabeled simulation",
            "telemetryZipSha256Before": digest(baseline),
            "telemetryZipSha256After": digest(exported),
            "captureIdentitiesAndRevisionsUnchanged": True,
            "telemetryManifest": manifest,
            "planningCsvSemanticSha256Before": digest(b"\n".join(before_csv)),
            "planningCsvSemanticSha256After": digest(b"\n".join(after_csv)),
            "planningComparison": "existing combined timeline CSV; generated-at header excluded",
            "simulationExportRejected": True,
        }
    finally:
        flight.close()
        service.store.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="operator-export-probe-") as directory:
        print(json.dumps(probe(Path(directory))))
