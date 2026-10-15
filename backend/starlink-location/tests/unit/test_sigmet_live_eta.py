"""Live crossings share POI speed blending and fail closed."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile
from app.models.route_sigmets import IntersectionSpan
from app.services.aviation_weather.route_encounters import (
    capture_encounter_plan,
    evaluate_encounters,
)

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
MS = int(NOW.timestamp() * 1000)


def route():
    return ParsedRoute(
        metadata=RouteMetadata(name="Live", file_path="live.kml", point_count=3),
        timing_profile=RouteTimingProfile(has_timing_data=True),
        points=[
            RoutePoint(
                latitude=0,
                longitude=i,
                sequence=i,
                expected_arrival_time=NOW + timedelta(minutes=(i - 1) * 10),
                expected_segment_speed_knots=360 if i == 1 else 240,
            )
            for i in range(3)
        ],
    )


def telemetry(*, longitude=0.5, speed=120, age=0, speed_age=0, now=NOW):
    return NS(
        position=NS(
            latitude=0,
            longitude=longitude,
            speed=speed,
            observed_at=now - timedelta(seconds=age),
            speed_observed_at=now - timedelta(seconds=speed_age),
        )
    )


def passage(segment=1, start=0.25, end=0.75):
    return IntersectionSpan(
        segment_index=segment,
        start_fraction=start,
        end_fraction=end,
        entry=[segment + start, 0],
        exit=[segment + end, 0],
        boundary_error_m=0,
    )


def live(*, phase="in_flight", sample=None, now=NOW):
    from app.services.aviation_weather.live_encounters import project_live_plan

    value = route()
    planned = capture_encounter_plan(value, "a" * 64, "ordinary", None)
    return project_live_plan(
        value, planned, phase, sample if sample is not None else telemetry(), now
    )


def test_delay_changes_validity_and_matches_poi_engine():
    from app.models.poi import POI
    from app.services.eta_calculator import ETACalculator

    result = evaluate_encounters(live(), [passage()], MS, MS + 480000)
    # .5 degree to waypoint1 at blended 240kt, then .25/.75 degree at 240kt.
    assert result.status == "no-overlap"
    assert result.spans[0].entry_ms == pytest.approx(MS + 675455, abs=2)
    assert result.spans[0].exit_ms == pytest.approx(MS + 1125759, abs=2)
    poi = POI(
        id="comparison",
        name="Projection",
        latitude=0,
        longitude=1.25,
        projected_latitude=0,
        projected_longitude=1.25,
        projected_waypoint_index=1,
        projected_route_progress=62.5,
    )
    eta = ETACalculator()._calculate_route_aware_eta_estimated(
        0, 0.5, poi, route(), 120
    )
    assert result.spans[0].entry_ms == pytest.approx(MS + eta * 1000, abs=2)
    planned = capture_encounter_plan(route(), "a" * 64, "ordinary", None)
    assert (
        evaluate_encounters(planned, [passage()], MS, MS + 480000).status == "overlap"
    )


def test_clock_and_speed_retime_without_plan_edit():
    first = live()
    later_time = NOW + timedelta(minutes=20)
    later = live(now=later_time, sample=telemetry(now=later_time))
    assert later.times_ms[2] - first.times_ms[2] == 1200000
    assert later.revision != first.revision
    assert live(sample=telemetry(speed=360)).times_ms[2] < first.times_ms[2]


@pytest.mark.parametrize(
    "sample",
    [
        telemetry(age=10),
        telemetry(speed_age=10),
        NS(),
        telemetry(speed=float("nan")),
        telemetry(speed=-1),
    ],
)
def test_unusable_live_inputs_never_fall_back_to_schedule(sample):
    result = evaluate_encounters(live(sample=sample), [passage()], MS, MS + 3600000)
    assert result.status == "unknown"
    assert result.spans[0].entry_ms is None


def test_predeparture_uses_plan_even_after_scheduled_departure():
    plan = live(phase="pre_departure", sample=NS())
    assert plan.method == "segment-linear-utc-v1"
    assert plan.times_ms[1] == MS


def test_passed_crossing_is_not_upcoming():
    result = evaluate_encounters(
        live(sample=telemetry(longitude=1.9)), [passage()], MS, MS + 3600000
    )
    assert result.status == "passed"
    assert result.spans[0].entry_ms is None


def test_inside_crossing_starts_now_and_projects_exit():
    result = evaluate_encounters(
        live(sample=telemetry(longitude=1.5)), [passage()], MS, MS + 3600000
    )
    assert result.status == "overlap"
    assert result.spans[0].entry_ms == MS
    assert result.spans[0].exit_ms > MS


def test_postarrival_has_no_upcoming_crossings():
    assert (
        evaluate_encounters(
            live(phase="post_arrival", sample=NS()), [passage()], MS, MS + 3600000
        ).status
        == "passed"
    )


def test_live_capture_uses_flight_phase_and_coordinator(monkeypatch):
    from app.services import flight_state
    from app.services.aviation_weather.live_encounters import capture_flight_encounters

    value = route()
    planned = capture_encounter_plan(value, "a" * 64, "ordinary", None)
    context = NS(route=value, encounter_plan=planned, source="ordinary")
    now = datetime.now(timezone.utc)
    state = NS(coordinator=NS(get_current_telemetry=lambda: telemetry(now=now)))
    monkeypatch.setattr(
        flight_state,
        "get_flight_state_manager",
        lambda: NS(get_status=lambda: NS(phase=NS(value="in_flight"))),
    )
    result = capture_flight_encounters(context, state)
    assert result.method == "route-estimated-utc-v1"
    assert result.times_ms[2] > int(now.timestamp() * 1000)
    assert result.revision != planned.revision


def test_replay_uses_published_mission_clock_without_live_speed(monkeypatch):
    from app.services.aviation_weather.live_encounters import capture_flight_encounters
    from app.simulation import run_timing

    value = route()
    planned = capture_encounter_plan(value, "a" * 64, "simulation", None)
    context = NS(
        route=value,
        encounter_plan=planned,
        source="simulation",
        route_id="route",
        run_id="run",
    )
    selection = (
        NS(route_id="route"),
        NS(progress_percent=75),
        NS(run_id="run", simulation_time=NOW + timedelta(minutes=5)),
    )
    monkeypatch.setattr(run_timing, "published_replay", lambda _: selection)
    result = capture_flight_encounters(context, NS())
    assert result.method == "mission-replay-utc-v1"
    assert result.reference_ms == MS + 300000
    assert result.times_ms == planned.times_ms
    assert (
        evaluate_encounters(result, [passage(end=0.4)], MS, MS + 3600000).status
        == "passed"
    )
    crossing = evaluate_encounters(result, [passage()], MS, MS + 3600000)
    assert crossing.spans[0].entry_ms == MS + 300000


def test_repeated_segment_current_occurrence_fails_closed():
    from app.services.aviation_weather.live_encounters import project_live_plan

    value = route()
    value.points[2].longitude = 0
    planned = capture_encounter_plan(value, "a" * 64, "ordinary", None)
    result = project_live_plan(value, planned, "in_flight", telemetry(), NOW)
    assert (
        evaluate_encounters(result, [passage(segment=0)], MS, MS + 3600000).status
        == "unknown"
    )


@pytest.mark.parametrize("missing_times", [True, False])
def test_replay_missing_times_and_progress_cannot_invent_completion(
    monkeypatch, missing_times
):
    from app.services.aviation_weather.live_encounters import capture_flight_encounters
    from app.simulation import run_timing

    value = route()
    if missing_times:
        for point in value.points:
            point.expected_arrival_time = None
    planned = capture_encounter_plan(value, "a" * 64, "simulation", None)
    context = NS(
        route=value,
        encounter_plan=planned,
        source="simulation",
        route_id="route",
        run_id="run",
    )
    selection = (NS(route_id="route"), NS(), NS(run_id="run", simulation_time=NOW))
    monkeypatch.setattr(run_timing, "published_replay", lambda _: selection)
    result = capture_flight_encounters(context, NS())
    assert (
        evaluate_encounters(result, [passage(segment=0)], MS, MS + 3600000).status
        == "unknown"
    )
