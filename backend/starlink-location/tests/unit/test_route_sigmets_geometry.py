"""Independent fixtures catch missed thin areas, holes, seam and unknown gaps."""

import importlib
import json
import math
from itertools import pairwise
from pathlib import Path

import pytest

FIXTURES = json.loads(
    (Path(__file__).parents[1] / "fixtures/route-sigmets/geometry.json").read_text()
)


def geometry():
    name = "app.services.aviation_weather.route_geometry"
    assert importlib.util.find_spec(
        name
    ), "conservative route geometry implementation missing"
    return importlib.import_module(name)


def feature(rings, identity="sigmet"):
    return {"id": identity, "geometry": {"type": "Polygon", "coordinates": rings}}


def rectangle(left, right, bottom=-1, top=1):
    return [[left, bottom], [right, bottom], [right, top], [left, top], [left, bottom]]


def equatorial_error(point, longitude):
    # Independent haversine distance to the exact equatorial crossing.
    lon, lat = map(math.radians, point)
    delta = lon - math.radians(longitude)
    return (
        2
        * 6371008.8
        * math.asin(
            math.sqrt(math.sin(lat / 2) ** 2 + math.cos(lat) * math.sin(delta / 2) ** 2)
        )
    )


@pytest.mark.parametrize("case", ["equator", "thin", "seam"])
def test_equatorial_crossing_has_analytic_spans(case):
    fixture = FIXTURES[case]
    advisory = feature([fixture.get("ring", rectangle(-1, 1))])
    if case == "seam":
        advisory["geometry"] = {
            "type": "MultiPolygon",
            "coordinates": [[ring] for ring in fixture["rings"]],
        }
    result = geometry().intersect_route(fixture["points"], [advisory])
    assert len(result.matches) == 1
    spans = result.matches[0].spans
    interiors = [s for s in spans if s.start_fraction < s.end_fraction]
    assert len(interiors) == 1
    span = interiors[0]
    # Exact boundary contacts may remain isolated when the inflated enclosure
    # cannot certify the short interval to the first interior witness.
    for contact in (s for s in spans if s.start_fraction == s.end_fraction):
        assert (
            min(abs(contact.start_fraction - f) for f in fixture["fractions"])
            * (4 * math.pi / 180 * 6371008.8)
            <= 18.52
        )
        assert not result.complete
        assert any(
            u.feature_id == "sigmet" and u.reason == "boundary-uncertain"
            for u in result.unresolved
        )
        rings = fixture.get("rings", [fixture.get("ring")])
        assert contact.entry == contact.exit
        assert contact.entry[1] == 0
        assert any(
            min(p[0] for p in ring) <= contact.entry[0] <= max(p[0] for p in ring)
            for ring in rings
        )
        assert (
            equatorial_error(
                contact.entry, fixture["points"][0][0] + 4 * contact.start_fraction
            )
            < 0.001
        )
    assert all(
        first.end_fraction <= last.start_fraction for first, last in pairwise(spans)
    )
    arc_length = 4 * math.pi / 180 * 6371008.8
    for actual, expected in zip(
        [span.start_fraction, span.end_fraction], fixture["fractions"]
    ):
        assert abs(actual - expected) * arc_length <= 18.52
    offset = fixture["points"][0][0]
    assert equatorial_error(span.entry, offset + 4 * fixture["fractions"][0]) <= 18.52
    assert equatorial_error(span.exit, offset + 4 * fixture["fractions"][1]) <= 18.52
    assert span.boundary_error_m <= 18.52


def test_containment_holes_and_disjoint_spans():
    module = geometry()
    area = feature(
        [rectangle(-4, 4), rectangle(-2, -1, -0.5, 0.5), rectangle(1, 2, -0.5, 0.5)]
    )
    result = module.intersect_route([[-3, 0], [3, 0]], [area])
    assert len(result.matches[0].spans) == 3
    for span, expected in zip(
        result.matches[0].spans, [(0, 1 / 6), (1 / 3, 2 / 3), (5 / 6, 1)]
    ):
        assert span.start_fraction == pytest.approx(expected[0], abs=18.52 / 667171)
        assert span.end_fraction == pytest.approx(expected[1], abs=18.52 / 667171)
    assert module.intersect_route([[-1.8, 0], [-1.2, 0]], [area]).matches == []
    contained = module.intersect_route([[-0.5, 0], [0.5, 0]], [area])
    assert contained.complete
    assert contained.matches[0].spans[0].start_fraction == 0
    assert contained.matches[0].spans[0].end_fraction == 1


def test_endpoint_contact_high_latitude_and_duplicate_points():
    module = geometry()
    touch = module.intersect_route([[-2, 0], [-1, 0]], [feature([rectangle(-1, 1)])])
    span = touch.matches[0].spans[0]
    assert span.start_fraction == span.end_fraction == 1
    fixture = FIXTURES["high_latitude"]
    result = module.intersect_route(fixture["points"], [feature([fixture["ring"]])])
    assert any(
        s.start_fraction <= 0.5 <= s.end_fraction for s in result.matches[0].spans
    )
    duplicate = module.intersect_route(
        [[-2, 0], [-2, 0], [2, 0]], [feature([rectangle(-1, 1)])]
    )
    assert duplicate.matches[0].spans[0].segment_index == 1


@pytest.mark.parametrize("points", [[[0, 0], [180, 0]], [[0, 0], [0, 0]], []])
def test_ambiguous_or_unusable_route_never_claims_disjoint(points):
    result = geometry().intersect_route(points, [feature([rectangle(-1, 1)])])
    assert not result.complete and result.reason
    assert result.unresolved[0].reason == "invalid-route"


def test_sub_tolerance_sliver_and_unlocated_are_explicitly_uncertain():
    result = geometry().intersect_route(
        [[-2, 0], [2, 0]],
        [
            feature([rectangle(0.123456789, 0.123456790)]),
            {"id": "unknown", "geometry": None},
        ],
    )
    assert not result.complete
    assert "sigmet" in {m.feature_id for m in result.matches} | {
        u.feature_id for u in result.unresolved
    }
    assert any(
        u.feature_id == "unknown" and u.reason == "unlocated" for u in result.unresolved
    )


def test_limits_never_truncate_to_success(monkeypatch):
    module = geometry()
    monkeypatch.setattr(module, "MAX_INTERVAL_VISITS", 1)
    result = module.intersect_route([[-2, 0], [2, 0]], [feature([rectangle(-1, 1)])])
    assert not result.complete and result.reason
    assert result.unresolved[0].reason == "limit"


def test_high_latitude_boundaries_have_independent_spherical_reference():
    fixture = FIXTURES["high_latitude"]
    result = geometry().intersect_route(fixture["points"], [feature([fixture["ring"]])])
    span = result.matches[0].spans[0]
    # Great-circle plane through the symmetric endpoints: tan(lat)=2*tan(60)*cos(lon).
    reference_lat = math.degrees(
        math.atan(2 * math.tan(math.pi / 3) * math.cos(math.pi / 180))
    )
    for actual, expected_lon in [(span.entry, -1), (span.exit, 1)]:
        lat1, lat2 = map(math.radians, [actual[1], reference_lat])
        dlon = math.radians(actual[0] - expected_lon)
        distance = (
            2
            * 6371008.8
            * math.asin(
                math.sqrt(
                    math.sin((lat1 - lat2) / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                )
            )
        )
        assert distance <= 18.52


def test_proven_spans_survive_unknown_sliver_without_bridging():
    result = geometry().intersect_route(
        [[-2, 0], [2, 0]],
        [
            {
                "id": "mixed",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [rectangle(-1, -0.5)],
                        [rectangle(0.123456789, 0.123456790)],
                        [rectangle(0.5, 1)],
                    ],
                },
            }
        ],
    )
    assert not result.complete
    spans = result.matches[0].spans
    interiors = [s for s in spans if s.start_fraction < s.end_fraction]
    assert len(interiors) == 2
    assert interiors[0].end_fraction < interiors[1].start_fraction
    assert all(s.end_fraction <= 0.375 or s.start_fraction >= 0.625 for s in spans)


def test_polygon_vertex_route_point_and_aggregate_span_caps(monkeypatch):
    module = geometry()
    with pytest.raises(ValueError):
        module.intersect_route([[0, 0]] * 20001, [])
    with pytest.raises(ValueError):
        module.intersect_route([[-2, 0], [2, 0]], [feature([[[0, 0]] * 100001])])
    monkeypatch.setattr(module, "MAX_SPANS", 1)
    result = module.intersect_route(
        [[-3, 0], [3, 0]], [feature([rectangle(-4, 4), rectangle(-1, 1, -0.5, 0.5)])]
    )
    assert not result.complete and result.reason == "limit"


def test_invalid_polygon_is_unlocated_not_disjoint():
    result = geometry().intersect_route(
        [[-3, 0], [3, 0]], [feature([rectangle(-4, 4), rectangle(-1, 1)])]
    )
    assert not result.complete
    assert result.unresolved[0].reason == "unlocated"


def test_sub_tolerance_hole_is_never_bridged_by_witnesses():
    result = geometry().intersect_route(
        [[0, 0], [0.0001, 0]],
        [feature([rectangle(-1, 1), rectangle(0.00002, 0.00003, -0.5, 0.5)])],
    )
    assert result.matches
    assert not any(
        span.start_fraction < 0.2 and span.end_fraction > 0.3
        for span in result.matches[0].spans
    )
    assert not result.complete
    assert result.unresolved[0].reason == "boundary-uncertain"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("first_right", [0.00001, 0.00006])
def test_terminal_witness_tails_preserve_unseen_component(reverse, first_right):
    # An 11.12 m arc has one/two sampled witnesses in the first component;
    # the separate 0.7..0.8 component lies in the unchecked suffix (prefix
    # when reversed). Its analytic contact must be matched or unresolved.
    points = [[0, 0], [0.0001, 0]]
    if reverse:
        points.reverse()
    result = geometry().intersect_route(
        points,
        [
            {
                "id": "two-pieces",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [rectangle(-0.00001, first_right)],
                        [rectangle(0.00007, 0.00008)],
                    ],
                },
            }
        ],
    )
    assert result.matches, "retain the legitimate observed component"
    start, end = (0.2, 0.3) if reverse else (0.7, 0.8)
    contact_preserved = any(
        span.start_fraction <= end and span.end_fraction >= start
        for match in result.matches
        for span in match.spans
    )
    unknown = any(
        u.feature_id == "two-pieces" and u.reason == "boundary-uncertain"
        for u in result.unresolved
    )
    assert contact_preserved or unknown
    if not contact_preserved:
        assert not result.complete


@pytest.mark.parametrize("normalized", [False, True])
def test_near_antipodal_polar_cap_never_becomes_definite_zero(normalized):
    cap = feature([rectangle(-180, 180, 89.999975, 90)], "polar-cap")
    if normalized:
        from app.services.aviation_weather.normalization import _split_geometry

        # This narrow ring is admitted by the existing unwrap/split constraints.
        # The exact shortest meridian at lon 0 passes through its interior.
        raw = {"type": "Polygon", "coordinates": [rectangle(-1, 1, 89.999975, 90)]}
        admitted, count = _split_geometry(raw, 100_000)
        assert count == 5
        cap["geometry"] = json.loads(json.dumps(admitted))
    result = geometry().intersect_route([[0, 45], [180, -44.99999999]], [cap])
    assert result.matches or (not result.complete and result.unresolved)
    assert not (result.complete and not result.matches)


@pytest.mark.parametrize("points", [[[0, 0], [0.0001, 0]], [[30, 70], [30, 70.00001]]])
def test_short_legs_still_certify_containment(points):
    lon, lat = points[0]
    result = geometry().intersect_route(
        points, [feature([rectangle(lon - 1, lon + 1, lat - 1, lat + 1)])]
    )
    assert result.complete and not result.unresolved
    assert len(result.matches[0].spans) == 1
    assert result.matches[0].spans[0].start_fraction == 0
    assert result.matches[0].spans[0].end_fraction == 1


@pytest.mark.parametrize("gap_degrees", [0.03, 0.1])
def test_resolved_near_antipodal_meridian_retains_analytic_match(gap_degrees):
    result = geometry().intersect_route(
        [[0, 45], [180, -45 + gap_degrees]], [feature([rectangle(-1, 1, 60, 61)])]
    )
    assert result.matches
    interior = max(
        result.matches[0].spans,
        key=lambda span: span.end_fraction - span.start_fraction,
    )
    length = math.radians(180 - gap_degrees) * 6371008.8
    assert abs(interior.start_fraction - 15 / (180 - gap_degrees)) * length <= 18.52
    assert abs(interior.end_fraction - 16 / (180 - gap_degrees)) * length <= 18.52
