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
