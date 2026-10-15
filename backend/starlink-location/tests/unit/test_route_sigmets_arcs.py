"""Analytic spherical references catch chord/endpoint-box approximations."""

import importlib
import math

import pytest


def arcs():
    name = "app.services.aviation_weather.route_arcs"
    assert importlib.util.find_spec(
        name
    ), "bounded great-circle arc implementation missing"
    return importlib.import_module(name)


def test_high_latitude_extremum_and_shortest_seam():
    module = arcs()
    arc = module.GreatCircleArc([-60, 60], [60, 60])
    # Independent plane intersection: tan(apex) = tan(60) / cos(60).
    expected = math.degrees(math.atan(math.tan(math.pi / 3) / math.cos(math.pi / 3)))
    assert arc.point(0.5) == pytest.approx([0, expected], abs=1e-10)
    assert max(b[3] for b in arc.enclosures(0, 1)) >= expected
    seam = module.GreatCircleArc([178, 0], [-178, 0])
    assert abs(abs(seam.point(0.5)[0]) - 180) < 1e-9
    assert len(seam.enclosures(0, 1)) == 2
    assert seam.length_m == pytest.approx(4 * math.pi / 180 * 6371008.8)


def test_pole_enclosure_and_antipodal_ambiguity():
    module = arcs()
    arc = module.GreatCircleArc([0, 80], [180, 80])
    boxes = arc.enclosures(0, 1)
    assert boxes[0][0] == -180 and boxes[0][2] == 180
    assert boxes[0][3] == 90
    with pytest.raises(ValueError, match="antipodal"):
        module.GreatCircleArc([0, 0], [180, 0])


@pytest.mark.parametrize("longitude", [0, 30, -120, 179])
def test_near_antipodal_enclosures_contain_independent_meridian(longitude):
    module = arcs()
    opposite = (longitude + 360) % 360 - 180
    arc = module.GreatCircleArc([longitude, 45], [opposite, -44.99999999])
    # Exact meridian: 45 degrees to the north pole, then 134.99999999 south.
    # These expectations do not use the production vector/tangent/extrema.
    pole_fraction = 45 / 179.99999999
    for left, right in [(0, 1), (pole_fraction - 1e-7, pole_fraction + 1e-7)]:
        boxes = arc.enclosures(left, right)
        for fraction in [left, pole_fraction, right]:
            angle = 45 + fraction * 179.99999999
            lon, lat = (longitude, angle) if angle <= 90 else (opposite, 180 - angle)
            assert any(
                west <= lon <= east and south <= lat <= north
                for west, south, east, north in boxes
            )


@pytest.mark.parametrize("gap_degrees", [0.03, 0.1])
def test_resolved_meridian_enclosures_contain_independent_dense_samples(gap_degrees):
    arc = arcs().GreatCircleArc([0, 45], [180, -45 + gap_degrees])
    for left, right in [(0, 1), (0.24, 0.26), (0.1, 0.2), (0.3, 0.8)]:
        boxes = arc.enclosures(left, right)
        for index in range(101):
            fraction = left + (right - left) * index / 100
            angle = 45 + fraction * (180 - gap_degrees)
            lon, lat = (0, angle) if angle <= 90 else (180, 180 - angle)
            assert any(
                west <= lon <= east and south <= lat <= north
                for west, south, east, north in boxes
            )
