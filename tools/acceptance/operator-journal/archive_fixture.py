"""Explicit synthetic inputs for #370; production stores, rendering and ZIP code."""

import json
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.mission import storage
from app.operator.models import CreateRecord, UpdateRecord
from app.services.flight_events.live_adapter import FlightEventRuntime
from app.mission.slide_cache.coordinator import start_runtime
from scenario import START, ScenarioClock, SyntheticRawReader, flight_observations

MISSION = "synthetic-mission-a"


def initialize(main, root):
    """Called after normal startup, and repeated idempotently on restart."""
    archive_root = root / "operator" / "archive-acceptance"
    archive_root.mkdir(parents=True, exist_ok=True)
    clock = ScenarioClock(START + timedelta(hours=3))
    # Register the real #349 lifecycle, driven exclusively by synthetic raw inputs.
    flight = FlightEventRuntime(archive_root / "synthetic-archive-flights")
    main.app.state.flight_event_runtime = flight
    marker = archive_root / "synthetic-archive-seeded.json"
    mission = storage.load_mission_v2(MISSION)
    if not marker.exists():
        for index, leg in enumerate(mission.legs):
            for observation in flight_observations(
                ScenarioClock(), MISSION, leg.id, offset=index * 3000
            ):
                flight.accept(observation)
        archival_clock = ScenarioClock(START + timedelta(hours=2))
        for _ in range(500):
            archival_clock.advance(300)
            flight.capture.backfill_one(SyntheticRawReader(), archival_clock.now())
            flight.capture.recover(archival_clock.now())
        captures = [flight.archive.capture(MISSION, leg.id) for leg in mission.legs]
        assert all(c and c["state"] == "sealed" for c in captures)
        with main.app.state.operator_binding.access() as runtime:
            runtime.clock.set(clock.now())
            service = runtime.service
            epoch = str(service.store.health().api_epoch)

            def save(kind, payload, *, scope="mission", leg_id=None, at=None, key=None):
                command = CreateRecord(
                    record_type=kind,
                    mission_id=MISSION,
                    scope=scope,
                    leg_id=leg_id,
                    time={
                        "occurred_at": at or START,
                        "precision": "exact",
                        "end_state": "instant",
                    },
                    payload={
                        "entry_type": "note" if kind == "journal_entry" else kind,
                        "title": "Synthetic archive " + (key or kind),
                        **payload,
                    },
                )
                return service.execute(
                    command,
                    key=str(uuid5(NAMESPACE_URL, "archive/" + (key or kind))),
                    epoch=epoch,
                ).saved_records[0]

            for i, scope in enumerate(
                ("preflight", "leg", "between_legs", "postflight")
            ):
                save(
                    "journal_entry",
                    {"note": "Wholly synthetic archive acceptance"},
                    scope=scope,
                    leg_id=mission.legs[0].id if scope == "leg" else None,
                    at=START + timedelta(minutes=(-10, 6, 30, 65)[i]),
                    key=scope,
                )
            conference = save(
                "conference", {"status": "established"}, key="reused conference"
            )
            for index in range(2):
                call = save(
                    "call",
                    {"status": "completed", "conference_id": str(conference.record_id)},
                    key=f"call {index}",
                )
                save(
                    "participation",
                    {
                        "state": "left",
                        "conference_id": str(conference.record_id),
                        "call_id": str(call.record_id),
                    },
                    key=f"participation {index}",
                )
            issue = save(
                "issue",
                {"status": "open", "update_text": "Synthetic initial observation"},
            )
            fields = {
                k: getattr(issue, k)
                for k in (
                    "record_type",
                    "mission_id",
                    "leg_id",
                    "scope",
                    "time",
                    "payload",
                )
            }
            fields["payload"] = issue.payload.model_dump(mode="json") | {
                "status": "resolved",
                "update_text": "Synthetic retrospective correction",
            }
            service.execute(
                UpdateRecord(
                    record_id=issue.record_id,
                    expected_version=issue.version,
                    audit_note="Synthetic retrospective resolution",
                    **fields,
                ),
                key=str(uuid5(NAMESPACE_URL, "archive/issue-correction")),
                epoch=epoch,
            )
            save(
                "transport_decision",
                {
                    "services": [
                        {
                            "row_id": str(uuid5(NAMESPACE_URL, "archive/transport")),
                            "service": "VTC",
                            "applied": {"transport": "Ka"},
                        }
                    ]
                },
            )
        marker.write_text(
            json.dumps(
                {"synthetic": True, "leg_revisions": [c["revision"] for c in captures]}
            )
        )
    else:
        with main.app.state.operator_binding.access() as runtime:
            runtime.clock.set(clock.now())
    # Persist the raw route used by the real model fixture so plan import has KML.
    manager = main.app.state.route_manager
    route = manager.get_route(mission.legs[0].route_id)
    points = route.points
    xml = ['<kml xmlns="http://www.opengis.net/kml/2.2"><Document>']
    for index, point in enumerate(points):
        stamp = point.expected_arrival_time.strftime("%Y-%m-%d %H:%M:%S")
        xml.append(
            f"<Placemark><name>SYN{index}</name><description>Time Over Waypoint: {stamp}Z</description><Point><coordinates>{point.longitude},{point.latitude},1000</coordinates></Point></Placemark>"
        )
    coordinates = " ".join(f"{p.longitude},{p.latitude},1000" for p in points)
    xml.append(
        f"<Placemark><LineString><coordinates>{coordinates}</coordinates></LineString></Placemark></Document></kml>"
    )
    path = Path(manager.routes_dir) / f"{route.route_id}.kml"
    content = "".join(xml)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)
    # Exercise the production customer briefing cache/render/assembly lifecycle.
    main.app.state.customer_pdf_coordinator = start_runtime(
        manager, main.app.state.poi_manager
    )
