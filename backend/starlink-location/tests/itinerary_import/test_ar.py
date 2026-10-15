"""AR resolution uses flight-relative offsets and immutable occurrences."""

from datetime import timedelta

from app.mission.planning.models import ItineraryAR
from app.models.route import RoutePoint, RouteWaypoint
from tests.planning.cases import ar_fields

from .test_association import START, leg, route


def fixture(dep_seconds=42, arrival_seconds=17):
    r = route(START + timedelta(seconds=dep_seconds))
    r.timing_profile.arrival_time = START + timedelta(hours=2, seconds=arrival_seconds)
    r.route_id = "invented-route"
    r.content_hash = "a" * 64
    r.ingestion_profile = "planning_v1"
    r.source_departure_time = r.timing_profile.departure_time
    times = [
        r.timing_profile.departure_time,
        START + timedelta(minutes=90, seconds=dep_seconds),
        START + timedelta(minutes=100, seconds=arrival_seconds),
        r.timing_profile.arrival_time,
    ]
    r.points = [
        RoutePoint(
            latitude=0,
            longitude=i,
            sequence=i,
            occurrence_id=f"p{i}",
            expected_arrival_time=t,
            timing_source="waypoint",
        )
        for i, t in enumerate(times)
    ]
    r.waypoints = [
        RouteWaypoint(
            name=n,
            role=role,
            latitude=0,
            longitude=i,
            order=i,
            point_sequence=i,
            occurrence_id=f"p{i}",
            expected_arrival_time=times[i],
        )
        for i, (n, role) in enumerate(
            [
                ("AAAA", "departure"),
                ("TRACK", "waypoint"),
                ("EXIT", "waypoint"),
                ("BBBB", "arrival"),
            ]
        )
    ]
    a = ItineraryAR(
        **ar_fields(
            track="TRACK",
            entry_time=START + timedelta(minutes=90),
            exit_time=START + timedelta(minutes=100),
        )
    )
    return leg().model_copy(update={"ar_rows": [a]}), r


def resolve(l, r):
    from app.mission.itinerary_import.ar import resolve_import_ars

    return resolve_import_ars(l, r)


def test_endpoint_offsets_keep_kml_seconds_and_pdf_provenance():
    l, r = fixture()
    result = resolve(l, r)
    assert result.issues == []
    row = result.rows[0]
    assert row.start_anchor.source_time == START + timedelta(minutes=90, seconds=42)
    assert row.end_anchor.source_time == START + timedelta(minutes=100, seconds=17)
    assert (
        result.evidence[row.id]["source_entry_time"]
        == l.ar_rows[0].entry_time.isoformat()
    )
    assert row.entry_time == l.ar_rows[0].entry_time


def test_missing_exit_uses_timed_segment_interpolation():
    l, r = fixture()
    r.points[2].timing_source = "interpolated"
    r.waypoints = [w for w in r.waypoints if w.name != "EXIT"]
    row = resolve(l, r).rows[0]
    assert row.end_anchor.source_time == START + timedelta(minutes=100, seconds=17)
    assert row.end_anchor.occurrence_id.startswith("segment:")


def test_minute_gap_accepts_unique_named_track():
    l, r = fixture()
    r.points[1].expected_arrival_time += timedelta(seconds=60)
    r.waypoints[1].expected_arrival_time = r.points[1].expected_arrival_time
    assert resolve(l, r).rows[0].start_anchor.source_time == START + timedelta(
        minutes=91, seconds=42
    )


def test_larger_track_supported_gap_and_duplicate_occurrence():
    l, r = fixture()
    r.points[1].expected_arrival_time -= timedelta(minutes=3)
    r.waypoints[1].expected_arrival_time = r.points[1].expected_arrival_time
    assert resolve(l, r).rows[0].start_anchor.source_time == START + timedelta(
        minutes=87, seconds=42
    )
    # Another visit to the same track cannot be selected solely by name.
    r.waypoints.append(r.waypoints[2].model_copy(update={"name": "TRACK"}))
    r.points[2].expected_arrival_time = START + timedelta(minutes=88, seconds=42)
    result = resolve(l, r)
    assert result.issues and result.rows[0].match_status == "ambiguous"


def test_reversed_derived_interval_is_not_clamped():
    l, r = fixture(arrival_seconds=-1200)
    result = resolve(l, r)
    assert result.issues
    assert result.rows[0].match_status == "unresolved"


def test_midnight_offsets():
    l, r = fixture()
    delta = timedelta(hours=13)
    l = l.model_copy(
        update={
            "departure_time": l.departure_time + delta,
            "arrival_time": l.arrival_time + delta,
            "ar_rows": [
                a.model_copy(
                    update={
                        "entry_time": a.entry_time + delta,
                        "exit_time": a.exit_time + delta,
                    }
                )
                for a in l.ar_rows
            ],
        }
    )
    r.timing_profile.departure_time += delta
    r.timing_profile.arrival_time += delta
    r.source_departure_time += delta
    for p in r.points:
        p.expected_arrival_time += delta
    for w in r.waypoints:
        w.expected_arrival_time += delta
    assert resolve(l, r).rows[0].start_anchor.source_time.day == 2


def test_missing_route_timing_returns_an_issue():
    l, r = fixture()
    r.timing_profile = None
    assert resolve(l, r).issues
