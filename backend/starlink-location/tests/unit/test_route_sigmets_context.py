"""The selected immutable route, rather than a replay clock, owns identity."""

import importlib
import threading
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint


def module():
    return importlib.import_module("app.services.aviation_weather.route_context")


def route(name="Route A", lon=10):
    return ParsedRoute(
        metadata=RouteMetadata(name=name, file_path="fixture.kml", point_count=2),
        points=[
            RoutePoint(longitude=0, latitude=0),
            RoutePoint(longitude=lon, latitude=20),
        ],
    )


def manager(value):
    return NS(
        get_active_route_id=lambda: "route-a" if value else None,
        get_active_route=lambda: value,
    )


@pytest.mark.parametrize(
    "args,want",
    [
        (
            ("ordinary", "route-a", None, None, [[0.0, 0.0], [10.0, 20.0]]),
            "81b5005f4d0711b931d6b0853b6fc923729764774718cd3f1ec3a582b64534a7",
        ),
        (
            (
                "simulation",
                "røute",
                "runtime-1",
                "run-1",
                [[-180.0, -90.0], [180.0, 90.0]],
            ),
            "ebb5168797fc4f6cd95dab3937a549ec1cf6ebd7acf6978f07c3ba90df3da05c",
        ),
    ],
)
def test_cross_language_pinned_digest(args, want):
    assert module().route_context_key(*args) == want


def test_zero_rename_and_ticking_do_not_change_identity():
    key = module().route_context_key
    assert key("ordinary", "route-a", None, None, [[0.0, -0.0], [10.0, 20.0]]) == key(
        "ordinary", "route-a", None, None, [[-0.0, 0.0], [10.0, 20.0]]
    )
    value = route()
    first = module().select_route_context(manager(value), None)
    value.metadata.name = "Renamed"
    value.points[1].altitude = 9000
    assert (
        module().select_route_context(manager(value), None).context_key
        == first.context_key
    )
    value.points.reverse()
    assert (
        module().select_route_context(manager(value), None).context_key
        != first.context_key
    )


@pytest.mark.parametrize(
    "points",
    [
        None,
        [[0.0, float("inf")]],
        [[181.0, 0.0]],
        [[0.0, 91.0]],
        [[True, 0.0]],
        [[0.0, 0.0]] * 20001,
    ],
)
def test_invalid_or_excessive_key_input_is_rejected(points):
    with pytest.raises(ValueError):
        module().route_context_key("ordinary", "route-a", None, None, points)


@pytest.mark.parametrize(
    "state", ["running", "completed", "cancelled", "failed", "idle"]
)
def test_only_current_selected_replay_artifacts_are_used(state):
    replay = route("Replay", 30)
    plan = NS(route_id="replay-route", artifacts=NS(route=replay))
    status = NS(
        state=state,
        runtime_id="runtime-1",
        run=NS(run_id="run-1", route_id="replay-route"),
    )
    service = NS(status=lambda: status, runtime=NS(selected_plan=lambda: plan))
    selected = module().select_route_context(manager(route()), service)
    assert selected.source == (
        "simulation" if state in ["running", "completed"] else "ordinary"
    )
    if selected.source == "simulation":
        assert selected.points[-1] == [30.0, 20.0]
        assert selected.runtime_id == "runtime-1" and selected.run_id == "run-1"
        original = selected.context_key
        status.run.run_id = "run-2"
        assert (
            module().select_route_context(manager(route()), service).context_key
            != original
        )
        status.run.route_id = "other-route"
        assert (
            module().select_route_context(manager(route()), service).source
            == "ordinary"
        )


def test_no_route_returns_none():
    assert module().select_route_context(manager(None), None) is None


def test_copy_is_locked_but_hashing_allows_concurrent_route_edit(monkeypatch):
    value = route()
    lock = threading.RLock()
    held = False

    @contextmanager
    def gate():
        nonlocal held
        with lock:
            held = True
            yield
            held = False

    original = module().route_context_key

    def hash_after_edit(*args):
        assert not held
        with lock:
            value.points[-1].longitude = 70
        return original(*args)

    monkeypatch.setattr(module(), "get_active_leg_lock", lambda: gate())
    monkeypatch.setattr(module(), "route_context_key", hash_after_edit)

    def active():
        assert held
        return value

    selected = module().select_route_context(
        NS(get_active_route_id=lambda: "route-a", get_active_route=active), None
    )
    assert selected.points[-1] == [10.0, 20.0]
    assert value.points[-1].longitude == 70
