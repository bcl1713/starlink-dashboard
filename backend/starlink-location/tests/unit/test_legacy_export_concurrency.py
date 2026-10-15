"""Overlapping legacy exports must preserve each mission's own PNG media."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from cartopy.mpl.geoaxes import GeoAxes

from app.mission.exporter import __main__ as exporter
from app.mission.models import MissionLegTimeline

pytest_plugins = ["tests.unit.test_export_snapshot"]


def test_overlapping_distinct_route_maps_match_their_serial_media(
    export_inputs, monkeypatch
):
    mission, routes, pois, _catalog = export_inputs
    route_b = routes._routes["r"].model_copy(deep=True)
    for point in route_b.points:
        point.longitude += 80 + point.sequence * 8
        point.latitude += 30
    routes._routes["b"] = route_b
    leg_a = mission.legs[0]
    leg_b = leg_a.model_copy(update={"id": "b", "route_id": "b"}, deep=True)
    timeline = MissionLegTimeline(mission_leg_id=leg_a.id, segments=[])
    # Avoid external Natural Earth downloads; actual route/labels/figures stay real.
    monkeypatch.setattr(GeoAxes, "coastlines", lambda *args, **kwargs: None)
    monkeypatch.setattr(GeoAxes, "add_feature", lambda *args, **kwargs: None)

    def render(leg):
        return exporter._generate_route_map(
            timeline, leg, route_manager=routes, poi_manager=pois
        )

    expected_a, expected_b = render(leg_a), render(leg_b)
    assert expected_a != expected_b
    original = exporter.plt.figure
    second_entered = threading.Event()
    count_lock = threading.Lock()
    calls = 0

    def overlap(*args, **kwargs):
        nonlocal calls
        figure = original(*args, **kwargs)
        with count_lock:
            calls += 1
            first = calls == 1
        if first:
            second_entered.wait(0.3)
        else:
            second_entered.set()
        return figure

    monkeypatch.setattr(exporter.plt, "figure", overlap)
    with ThreadPoolExecutor(max_workers=2) as workers:
        a, b = workers.submit(render, leg_a), workers.submit(render, leg_b)
        actual_a, actual_b = a.result(timeout=30), b.result(timeout=30)
    assert actual_a == expected_a, "first export received the other request's map"
    assert actual_b == expected_b, "second export received the other request's map"


def test_cancelled_request_does_not_wait_for_another_requests_plot(monkeypatch):
    from app.mission.exporter.export_cancel import ExportCancelled
    from app.mission.exporter.plot_ownership import PLOT_LOCK, export_plot_context

    cancel = threading.Event()

    @export_plot_context
    def render(*, cancel):
        return exporter._generate_timeline_chart(
            MissionLegTimeline(mission_leg_id="empty", segments=[])
        )

    def forbidden(*args, **kwargs):
        pytest.fail("cancelled waiting request created a figure")

    monkeypatch.setattr(exporter.plt, "subplots", forbidden)
    with ThreadPoolExecutor(max_workers=1) as workers, PLOT_LOCK:
        result = workers.submit(render, cancel=cancel)
        cancel.set()
        with pytest.raises(ExportCancelled):
            result.result(timeout=1)
