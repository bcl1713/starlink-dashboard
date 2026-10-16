"""Analytic spherical crossings with hand-derived geographic expectations."""

from math import pi

import pytest

from app.services.pop.geometry import PopGeometryError, find_crossings, nearest_pop
from app.services.pop.models import PopCatalog, PopSite, RouteVertex


def catalog(*locations):
    return PopCatalog(
        sites=tuple(
            PopSite(
                id=name,
                city=name,
                country="US",
                latitude=lat,
                longitude=lon,
                aliases=(),
                source="test",
                coordinate_source="test",
            )
            for name, lat, lon in locations
        ),
        fingerprint="fixture",
    )


def route(*positions):
    return tuple(RouteVertex(latitude=lat, longitude=lon) for lat, lon in positions)


def two_sites():
    return catalog(("a", 0, -10), ("b", 0, 10))


def test_equatorial_boundary():
    (crossing,) = find_crossings(route((0, -5), (0, 5)), two_sites(), "r")
    assert (crossing.from_pop_id, crossing.to_pop_id, crossing.segment_index) == (
        "a",
        "b",
        0,
    )
    assert crossing.fraction == pytest.approx(0.5, abs=1e-8)
    assert crossing.latitude == pytest.approx(0, abs=1e-8)
    assert crossing.longitude == pytest.approx(0, abs=1e-8)
    assert crossing.distance_meters == pytest.approx(6371000 * pi / 36)


def test_three_regions_in_one_leg_including_very_short_middle_region():
    sites = catalog(("a", 0, -0.00001), ("b", 0, 0), ("c", 0, 0.00001))
    crossings = find_crossings(route((0, -30), (0, 30)), sites, "r")
    assert [(c.from_pop_id, c.to_pop_id) for c in crossings] == [("a", "b"), ("b", "c")]
    assert [c.longitude for c in crossings] == pytest.approx(
        [-0.000005, 0.000005], abs=1e-8
    )


def test_antimeridian_minor_arc():
    sites = catalog(("a", 0, 170), ("b", 0, -170))
    (crossing,) = find_crossings(route((0, 175), (0, -175)), sites, "r")
    assert crossing.fraction == pytest.approx(0.5, abs=1e-8)
    assert abs(crossing.longitude) == pytest.approx(180, abs=1e-8)
    assert crossing.distance_meters == pytest.approx(6371000 * pi / 36)


def test_tangent_at_route_vertex_does_not_change_region():
    assert find_crossings(route((0, -5), (0, 0), (0, -5)), two_sites(), "r") == ()


def test_sustained_tie_is_indeterminate():
    sites = catalog(("a", 10, 0), ("b", -10, 0))
    with pytest.raises(PopGeometryError) as exc:
        find_crossings(route((0, -5), (0, 5)), sites, "r")
    assert exc.value.reason


def test_antipodal_leg_is_indeterminate():
    with pytest.raises(PopGeometryError):
        find_crossings(route((0, 0), (0, 180)), two_sites(), "r")


def test_reentry_has_distinct_stable_revision_scoped_occurrence_ids():
    vertices = route((0, -5), (0, 5), (0, -5), (0, 5))
    crossings = find_crossings(vertices, two_sites(), "r")
    assert [(c.from_pop_id, c.to_pop_id) for c in crossings] == [
        ("a", "b"),
        ("b", "a"),
        ("a", "b"),
    ]
    assert len({c.id for c in crossings}) == 3
    assert crossings == find_crossings(vertices, two_sites(), "r")
    assert {c.id for c in crossings}.isdisjoint(
        c.id for c in find_crossings(vertices, two_sites(), "new")
    )
    assert [c.distance_meters for c in crossings] == pytest.approx(
        [6371000 * pi / 36 * x for x in (1, 3, 5)]
    )


def test_repeated_vertices_and_boundary_vertex_emit_once():
    (crossing,) = find_crossings(
        route((0, -5), (0, -5), (0, 0), (0, 0), (0, 5)), two_sites(), "r"
    )
    assert crossing.segment_index == 3
    assert crossing.fraction == pytest.approx(0)
    assert crossing.distance_meters == pytest.approx(6371000 * pi / 36)


@pytest.mark.parametrize("vertices", [(), route((0, 0)), route((0, -5), (0, -5))])
def test_empty_singleton_or_stationary_route_has_no_crossings(vertices):
    assert find_crossings(vertices, two_sites(), "r") == ()


def test_single_site_and_nonwinning_boundaries_produce_no_crossings():
    assert find_crossings(route((0, -30), (0, 30)), catalog(("a", 45, 90)), "r") == ()
    sites = catalog(("a", 0, 0), ("b", 60, -10), ("c", 60, 10))
    assert find_crossings(route((0, -5), (0, 5)), sites, "r") == ()


def test_nearest_tie_retains_only_tied_previous_id_and_switches_uniquely():
    sites = two_sites()
    assert nearest_pop(0, 0, sites) is None
    assert nearest_pop(0, 0, sites, "b") == "b"
    assert nearest_pop(0, 0, sites, "unknown") is None
    assert nearest_pop(0, 0.001, sites, "a") == "b"
    initial = min(s.id for s in sites.sites)
    assert nearest_pop(0, 0, sites, initial) == "a"


def test_curved_high_latitude_leg_crosses_on_great_circle():
    sites = catalog(("a", 60, -20), ("b", 60, 20))
    (crossing,) = find_crossings(route((60, -10), (60, 10)), sites, "r")
    assert crossing.fraction == pytest.approx(0.5, abs=1e-8)
    assert crossing.latitude == pytest.approx(60.3783481248, abs=1e-8)
    assert crossing.longitude == pytest.approx(0, abs=1e-8)


@pytest.mark.parametrize("lat, lon", [(91, 0), (0, float("nan"))])
def test_invalid_query_position_cannot_select_a_pop(lat, lon):
    with pytest.raises(ValueError):
        nearest_pop(lat, lon, two_sites())


def test_crossing_carries_captured_catalog_display_cities_and_old_wire_defaults():
    from app.services.pop.models import PopCrossing

    sites = two_sites()
    sites = sites.model_copy(
        update={
            "sites": (
                sites.sites[0].model_copy(update={"city": "City Alpha"}),
                sites.sites[1].model_copy(update={"city": "City Beta"}),
            )
        }
    )
    (crossing,) = find_crossings(route((0, -5), (0, 5)), sites, "r")
    payload = crossing.model_dump(mode="json")
    assert payload["from_city"] == "City Alpha"
    assert payload["to_city"] == "City Beta"
    del payload["from_city"], payload["to_city"]
    old = PopCrossing.model_validate(payload)
    assert old.from_city is None and old.to_city is None
