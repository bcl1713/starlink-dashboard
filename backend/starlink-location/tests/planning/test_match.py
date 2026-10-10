from datetime import datetime

import pytest
from app.mission.planning.match import (
    ar_match_candidates,
    match_ar_windows,
    resolve_anchor,
)
from app.mission.planning.models import ExpectedLeg, ItineraryAR
from app.services.kml.parser import parse_kml_file
from app.services.kml.validator import KMLParseError


def utc(time):
    return datetime.fromisoformat("2026-10-25T" + time + "+00:00")


def kml_fixture(tmp_path, *, ambiguous=False, alternate=True, repeat=True):
    points = (
        [
            ("AAAA", 0, 0, "09:00:00"),
            ("P", 1, 0, "10:00:20"),
            ("Q", 2, 1, "10:30:00"),
            ("P", 1, 0, "11:00:40"),
            ("BBBB", 3, 0, "12:00:00"),
        ]
        if repeat
        else [
            ("AAAA", 179, 0, "09:00:00"),
            ("P", -179, 0, "10:00:20"),
            ("BBBB", -177, 0, "12:00:00"),
        ]
    )
    xml = [
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>AAAA-BBBB</name>'
    ]
    for name, lon, lat, time in points:
        xml.append(
            f"<Placemark><name>{name}</name><description>Time Over Waypoint: 2026-10-25 {time}Z</description><Point><coordinates>{lon},{lat},1000</coordinates></Point></Placemark>"
        )
        if name == "Q":  # duplicate representation, same time and position
            xml.append(xml[-1])

    def seg(coords, color="ffddad05"):
        xml.append(
            f"<Placemark><Style><LineStyle><color>{color}</color></LineStyle></Style><LineString><coordinates>{coords}</coordinates></LineString></Placemark>"
        )

    # Single ordered segment makes repeated visits explicit; untimed intermediate vertex.
    coords = " ".join(f"{lon},{lat},1000" for _, lon, lat, _ in points)
    seg(coords)
    if ambiguous:
        seg(coords)
    if alternate:
        seg("1,0,1000 50,50,1000", "ffb3b3b3")
        xml.append(
            "<Placemark><name>ALT</name><styleUrl>#altWaypointIcon</styleUrl><description>Time Over Waypoint: 2026-10-25 15:00:00Z</description><Point><coordinates>1,0,1000</coordinates></Point></Placemark>"
        )
    xml.append("</Document></kml>")
    path = tmp_path / "synthetic.kml"
    path.write_text("".join(xml))
    return path


def leg(entry="10:00:00", exit="11:00:00", precision="minute"):
    return ExpectedLeg(
        id="leg",
        ordinal=1,
        departure_airport="AAAA",
        arrival_airport="BBBB",
        departure_time=utc("09:00:00"),
        arrival_time=utc("12:00:00"),
        ar_section_status="listed",
        ar_rows=[
            ItineraryAR(
                id="ar",
                track="SYNTH",
                entry_time=utc(entry),
                exit_time=utc(exit),
                source_time_precision=precision,
            )
        ],
    )


def test_primary_route_excludes_alternates(tmp_path):
    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    assert len(route.points) == 5
    assert route.points[1].expected_arrival_time == utc("10:00:20")
    assert all(w.role != "alternate" for w in route.waypoints)
    assert route.timing_profile.arrival_time == utc("12:00:00")


def test_duplicate_same_position_collapses_but_repeat_occurrence_survives(tmp_path):
    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    visits = [p for p in route.points if p.longitude == 1 and p.latitude == 0]
    assert [p.expected_arrival_time for p in visits] == [
        utc("10:00:20"),
        utc("11:00:40"),
    ]
    assert visits[0].occurrence_id != visits[1].occurrence_id
    matched = match_ar_windows(leg(), route)[0]
    assert matched.match_status == "matched"
    assert matched.end_anchor.occurrence_id == visits[1].occurrence_id
    assert matched.end_anchor.source_time == utc("11:00:40")
    assert len([w for w in route.waypoints if w.name == "Q"]) == 1


def test_interpolated_antimeridian_anchor(tmp_path):
    route = parse_kml_file(kml_fixture(tmp_path, repeat=False), profile="planning_v1")
    matched = match_ar_windows(leg("09:30:00", "11:00:00", "second"), route)[0]
    assert matched.match_status == "matched"
    assert abs(matched.start_anchor.longitude) > 179
    assert 0 < matched.start_anchor.fraction < 1


def test_departure_delta_applied_once_fixed_and_elapsed(tmp_path):
    from app.mission.timeline_builder.calculator import route_with_adjusted_departure

    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    anchor = match_ar_windows(leg(), route)[0].start_anchor
    adjustment = utc("09:15:00")
    shifted = route_with_adjusted_departure(route, adjustment)
    assert resolve_anchor(anchor, route, adjustment) == utc("10:15:20")
    assert resolve_anchor(anchor, shifted, adjustment) == utc("10:15:20")
    twice = route_with_adjusted_departure(shifted, adjustment)
    assert twice.points[1].expected_arrival_time == utc("10:15:20")
    assert resolve_anchor(
        anchor.model_copy(update={"timing_mode": "fixed_utc"}), shifted, adjustment
    ) == utc("10:00:20")
    assert resolve_anchor(
        anchor.model_copy(update={"timing_mode": "elapsed", "elapsed_seconds": 600}),
        shifted,
        adjustment,
    ) == utc("09:25:00")


def test_ambiguous_primary_chain_is_rejected(tmp_path):
    with pytest.raises(KMLParseError, match="[Aa]mbiguous"):
        parse_kml_file(kml_fixture(tmp_path, ambiguous=True), profile="planning_v1")


def test_missing_matches_remain_unresolved(tmp_path):
    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    expected = leg()
    # Match requests need not use the expected card's span as a timing substitute.
    expected.ar_rows[0].entry_time = utc("08:00:00")
    assert match_ar_windows(expected, route)[0].match_status == "unresolved"
    assert not ar_match_candidates(expected, route)[0].start_candidates


def interleaved_kml(tmp_path, *, dwell=False):
    """Planner emits waypoint/segment/waypoint, including zero-length aliases."""
    visits = [
        ("AAAA", 0, "09:00:00"),
        ("P", 1, "10:00:00"),
        ("P_ALIAS", 1, "10:05:00" if dwell else "10:00:00"),
        ("BBBB", 2, "12:00:00"),
    ]
    xml = [
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>AAAA-BBBB</name>'
    ]
    for i, (name, lon, time) in enumerate(visits):
        if i:
            previous = visits[i - 1][1]
            xml.append(
                f"<Placemark><Style><LineStyle><color>ffddad05</color></LineStyle></Style><LineString><coordinates>{previous},0,1000 {lon},0,1000</coordinates></LineString></Placemark>"
            )
        xml.append(
            f"<Placemark><name>{name}</name><styleUrl>#destWaypointIcon</styleUrl><description>Time Over Waypoint: 2026-10-25 {time}Z</description><Point><coordinates>{lon},0,1000</coordinates></Point></Placemark>"
        )
    xml.append(
        "<Placemark><name>BBBB</name><styleUrl>#altWaypointIcon</styleUrl><description>Time Over Waypoint: 2026-10-25 08:30:00Z</description><Point><coordinates>2,0,1000</coordinates></Point></Placemark></Document></kml>"
    )
    path = tmp_path / "interleaved.kml"
    path.write_text("".join(xml))
    return path


@pytest.mark.parametrize("dwell", [False, True])
def test_interleaved_zero_length_alias_and_alternate_airport(tmp_path, dwell):
    route = parse_kml_file(
        interleaved_kml(tmp_path, dwell=dwell), profile="planning_v1"
    )
    assert len(route.points) == (4 if dwell else 3)
    assert route.points[-1].expected_arrival_time == utc("12:00:00")
    if dwell:
        assert route.points[1].expected_arrival_time == utc("10:00:00")
        assert route.points[2].expected_arrival_time == utc("10:05:00")


def test_partial_segment_vertices_interpolate(tmp_path):
    path = kml_fixture(tmp_path, repeat=False)
    path.write_text(
        path.read_text().replace(
            "179,0,1000 -179,0,1000", "179,0,1000 180,0,1000 -179,0,1000"
        )
    )
    route = parse_kml_file(path, profile="planning_v1")
    assert route.points[1].expected_arrival_time == utc("09:30:10")
    matched = match_ar_windows(leg("09:35:00", "09:40:00", "second"), route)[0]
    assert matched.start_anchor.segment_index == matched.end_anchor.segment_index
    assert resolve_anchor(matched.start_anchor, route, utc("09:10:00")) == utc(
        "09:45:00"
    )


def test_profile_resolver_precedes_restart_load(tmp_path):
    from app.services.route_manager import RouteManager

    directory = tmp_path / "routes"
    directory.mkdir()
    path = kml_fixture(directory)
    calls = []

    def profile(route_id):
        calls.append(route_id)
        return "planning_v1"

    manager = RouteManager(directory, profile_resolver=profile)
    manager._load_existing_routes()
    # Resolve before parsing and again before publication; reads revalidate too.
    assert len(calls) >= 2 and set(calls) == {path.stem}
    before_read = len(calls)
    route = manager.get_route(path.stem)
    assert len(calls) > before_read and set(calls) == {path.stem}
    assert route.ingestion_profile == "planning_v1"
    assert route.points[3].expected_arrival_time == utc("11:00:40")
    manager._profile_resolver = lambda _: None
    manager._load_route_file(str(path))
    assert path.stem in manager.get_route_errors()
    assert manager.get_route(path.stem) is None


def test_anchored_aar_and_swap_use_occurrences(tmp_path):
    from app.mission.models import AARWindow, MissionLeg, TransportConfig, XTransition
    from app.mission.timeline_builder.aar import (
        apply_x_transitions,
        resolve_aar_windows,
    )
    from app.mission.timeline_builder.calculator import (
        RouteTemporalProjector,
        route_with_adjusted_departure,
    )
    from app.satellites.rules import RuleEngine

    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    ar = match_ar_windows(leg(), route)[0]
    adjustment = utc("09:15:00")
    shifted = route_with_adjusted_departure(route, adjustment)
    mission = MissionLeg(
        id="synthetic",
        name="Synthetic",
        route_id=route.route_id,
        adjusted_departure_time=adjustment,
        transports=TransportConfig(
            initial_x_satellite_id="test-satellite",
            aar_windows=[
                AARWindow(
                    id="ar",
                    start_waypoint_name="P",
                    end_waypoint_name="P",
                    start_anchor=ar.start_anchor,
                    end_anchor=ar.end_anchor,
                )
            ],
            x_transitions=[
                XTransition(
                    id="swap",
                    latitude=0,
                    longitude=1,
                    target_satellite_id="test-satellite",
                    anchor=ar.end_anchor,
                )
            ],
        ),
    )
    projector = RouteTemporalProjector(
        shifted,
        shifted.timing_profile.departure_time,
        shifted.timing_profile.arrival_time,
    )
    windows = resolve_aar_windows(mission, shifted, projector)
    assert windows[0].start_time == utc("10:15:20")
    assert windows[0].end_time == utc("11:15:40")
    schedule = apply_x_transitions(RuleEngine(), mission, projector, windows)
    assert schedule[-1][0] == utc("11:15:40")


def test_zero_line_without_colocated_time_evidence_does_not_create_dwell(tmp_path):
    path = interleaved_kml(tmp_path)
    text = path.read_text()
    marker = "<Placemark><Style><LineStyle><color>ffddad05</color></LineStyle></Style><LineString><coordinates>1,0,1000 2,0,1000</coordinates></LineString></Placemark>"
    zero = marker.replace("1,0,1000 2,0,1000", "1,0,1000 1,0,1000")
    path.write_text(text.replace(marker, zero + marker))
    route = parse_kml_file(path, profile="planning_v1")
    assert len(route.points) == 3


def test_same_minute_occurrence_candidates_are_ambiguous(tmp_path):
    path = kml_fixture(tmp_path)
    path.write_text(path.read_text().replace("10:30:00", "10:00:40"))
    route = parse_kml_file(path, profile="planning_v1")
    candidates = ar_match_candidates(leg(), route)[0]
    assert len(candidates.start_candidates) == 2
    assert match_ar_windows(leg(), route)[0].match_status == "ambiguous"


def test_unmapped_primary_timestamp_is_rejected(tmp_path):
    path = kml_fixture(tmp_path)
    ghost = "<Placemark><name>GHOST</name><description>Time Over Waypoint: 2026-10-25 10:40:00Z</description><Point><coordinates>30,30,1000</coordinates></Point></Placemark>"
    path.write_text(path.read_text().replace("</Document>", ghost + "</Document>"))
    with pytest.raises(KMLParseError, match="mapping"):
        parse_kml_file(path, profile="planning_v1")


def test_fixed_anchor_aar_and_half_open_exit(tmp_path):
    from app.mission.models import AARWindow, MissionLeg, TransportConfig
    from app.mission.timeline_builder.aar import (
        _falls_within_window,
        resolve_aar_windows,
    )
    from app.mission.timeline_builder.calculator import (
        RouteTemporalProjector,
        route_with_adjusted_departure,
    )

    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    ar = match_ar_windows(leg(), route)[0]
    start = ar.start_anchor.model_copy(update={"timing_mode": "fixed_utc"})
    end = ar.end_anchor.model_copy(update={"timing_mode": "fixed_utc"})
    shifted = route_with_adjusted_departure(route, utc("09:15:00"))
    mission = MissionLeg(
        id="fixed",
        name="Fixed",
        route_id=route.route_id,
        transports=TransportConfig(
            initial_x_satellite_id="test-satellite",
            aar_windows=[
                AARWindow(
                    id="ar",
                    start_waypoint_name="P",
                    end_waypoint_name="P",
                    start_anchor=start,
                    end_anchor=end,
                )
            ],
        ),
    )
    projector = RouteTemporalProjector(
        shifted,
        shifted.timing_profile.departure_time,
        shifted.timing_profile.arrival_time,
    )
    windows = resolve_aar_windows(mission, shifted, projector)
    assert windows[0].start_time == utc("10:00:20")
    assert windows[0].end_time == utc("11:00:40")
    assert _falls_within_window(windows[0].start_time, windows)
    assert not _falls_within_window(windows[0].end_time, windows)


def test_route_content_identity_hashes_exact_uploaded_bytes(tmp_path):
    from hashlib import sha256

    path = kml_fixture(tmp_path)
    payload = path.read_bytes().replace(b"><", b">\r\n<")
    path.write_bytes(payload)
    route = parse_kml_file(path, profile="planning_v1")
    assert route.content_hash == sha256(payload).hexdigest()


def test_large_ordered_primary_route_does_not_use_recursive_mapping(tmp_path):
    from datetime import timedelta

    visits = []
    coords = []
    for i in range(1050):
        time = (utc("09:00:00") + timedelta(seconds=i * 3)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        name = "AAAA" if i == 0 else "BBBB" if i == 1049 else f"SYNTH{i}"
        coords.append(f"{i/10000},0,1000")
        visits.append(
            f"<Placemark><name>{name}</name><description>Time Over Waypoint: {time}Z</description><Point><coordinates>{coords[-1]}</coordinates></Point></Placemark>"
        )
    payload = (
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>AAAA-BBBB</name>'
        + "".join(visits)
        + "<Placemark><LineString><coordinates>"
        + " ".join(coords)
        + "</coordinates></LineString></Placemark></Document></kml>"
    )
    path = tmp_path / "large.kml"
    path.write_text(payload)
    route = parse_kml_file(path, profile="planning_v1")
    assert len(route.points) == 1050
    assert route.points[-1].expected_arrival_time == utc("09:52:27")


def test_route_bound_anchor_rejects_changed_time_or_occurrence(tmp_path):
    from app.mission.planning.match import RouteAnchorError

    route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
    anchor = match_ar_windows(leg(), route)[0].start_anchor
    with pytest.raises(RouteAnchorError):
        resolve_anchor(
            anchor.model_copy(update={"source_time": utc("10:30:00")}), route
        )
    interpolated = match_ar_windows(leg("09:30:00", "10:30:00", "second"), route)[
        0
    ].start_anchor
    with pytest.raises(RouteAnchorError):
        resolve_anchor(
            interpolated.model_copy(update={"occurrence_id": "forged"}), route
        )


def test_interpolated_vertex_is_not_an_explicit_same_minute_candidate(tmp_path):
    path = kml_fixture(tmp_path, repeat=False)
    path.write_text(
        path.read_text().replace(
            "179,0,1000 -179,0,1000", "179,0,1000 -179.0001,0,1000 -179,0,1000"
        )
    )
    route = parse_kml_file(path, profile="planning_v1")
    matched = match_ar_windows(leg("10:00:00", "11:00:00"), route)[0]
    assert matched.match_status == "matched"
    assert matched.start_anchor.source_time == utc("10:00:20")


@pytest.mark.parametrize(
    "coordinate", ["999,0,1000", "0,999,1000", "nan,0,1000", "0,0,inf"]
)
def test_planning_invalid_geometry_is_a_typed_input_error(tmp_path, coordinate):
    path = interleaved_kml(tmp_path)
    path.write_text(path.read_text().replace("0,0,1000", coordinate))
    with pytest.raises(KMLParseError):
        parse_kml_file(path, profile="planning_v1")


def minute_candidate_dto(tmp_path):
    """Synthetic public DTO shared with the AR review component regression."""
    from app.mission.planning.models import RouteBinding

    path = kml_fixture(tmp_path)
    path.write_bytes(
        path.read_bytes()
        .replace(b"10:00:20", b"10:00:30")
        .replace(b"11:00:40", b"11:00:30")
    )
    route = parse_kml_file(path, profile="planning_v1")
    route.route_id = "synthetic-minute-route"
    expected = leg()
    expected.route = RouteBinding(
        route_id=route.route_id,
        source_id=route.route_id,
        content_hash=route.content_hash,
        filename="synthetic.kml",
    )
    expected.ar_rows[0].source_altitude = 210
    expected.ar_rows[0].confirmed_units = "flight_level"
    expected.ar_rows[0].source_text = "Synthetic PDF AR source"
    expected.ar_rows = match_ar_windows(expected, route)
    return expected.model_dump(mode="json")


def test_minute_candidate_matches_frontend_contract_fixture(tmp_path):
    import json
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parents[4]
        / "frontend/mission-planner/src/components/planning/minute-candidate.fixture.json"
    )
    assert minute_candidate_dto(tmp_path) == json.loads(fixture.read_text())
