"""Synthetic dependency injection; only the isolated acceptance Compose loads this."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.responses import Response

if os.environ.get("POP_EVIDENCE_FIXTURE") != "synthetic-local-only":
    raise RuntimeError("Explicit isolated synthetic fixture required")

import main
from app.services import ground_entry_point as gep
from app.mission.models import MissionLegTimeline, TimelineSegment

clock = [0.0]
case = ["tokyo"]
scenario_time = [datetime.now(timezone.utc)]


def ip_sample():
    if case[0] == "window":
        return "216.255.176.42"
    return (
        "192.0.2.42"
        if case[0] in {"geoip", "changed-failure", "stale"}
        else "216.255.181.42"
    )


def geoip(ip):
    if case[0] in {"mapped-failure", "changed-failure"}:
        return None
    return gep.GroundEntryPoint(ip, "Invented Domestic City", "US", 33, -84)


resolver = gep.GroundEntryPointResolver(
    ip_resolver=ip_sample, geolocator=geoip, time_source=lambda: clock[0]
)
gep._resolver = resolver
original_lifespan = main.app.router.lifespan_context


@asynccontextmanager
async def fixture_lifespan(app):
    async with original_lifespan(app):
        coordinator = main._coordinator
        original_telemetry = coordinator.get_current_telemetry

        def telemetry():
            data = original_telemetry().model_copy(deep=True)
            data.timestamp = datetime.now(timezone.utc)
            # Invented position centers the synthetic map on the Tokyo marker.
            data.position.latitude, data.position.longitude = (
                (34, 140) if case[0] in {"tokyo", "mapped-failure"} else (33, -84)
            )
            return data

        coordinator.get_current_telemetry = telemetry
        app.state.pop_status_service.observation_provider = observation
        app.state.pop_status_service.config_provider = lambda: (
            coordinator.get_config().model_copy(update={"mode": "live"})
        )
        original_status = app.state.pop_status_service.status_payload

        def status_payload(*args, **kwargs):
            payload = original_status(*args, **kwargs)
            if case[0] in {"window", "skipped", "mismatch", "early"}:
                payload.update(lifecycle_payload())
            return payload

        app.state.pop_status_service.status_payload = status_payload
        yield


def observation(*args):
    if case[0] != "stale":
        resolver.refresh(force=True)
    gep.publish_ground_entry_point_metrics(resolver.current())
    return resolver.observation()


def lifecycle_payload():
    """Inject invented forecasts through the shipped evaluator for UI controls."""
    from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
    from app.services.pop.live import evaluate_live
    from app.services.pop.models import (
        PopCrossing,
        PopForecast,
        PopLiveState,
        PopTransition,
    )

    catalog = load_catalog(DEFAULT_CATALOG_PATH)
    base = scenario_time[0]

    def transition(id, source, target, minute, distance):
        center = base + timedelta(minutes=minute)
        return PopTransition(
            crossing=PopCrossing(
                id=id,
                from_pop_id=source,
                to_pop_id=target,
                from_city=source,
                to_city=target,
                segment_index=0,
                fraction=0.5,
                latitude=0,
                longitude=0,
                distance_meters=distance,
            ),
            crossing_utc=center,
            window_start_utc=center - timedelta(minutes=5),
            window_end_utc=center + timedelta(minutes=5),
        )

    if case[0] == "skipped":
        transitions = (
            transition("first", "los-angeles", "dallas", -30, 1),
            transition("second", "dallas", "tokyo", -10, 2),
        )
    else:
        transitions = (
            transition(
                "first",
                "los-angeles",
                "tokyo" if case[0] == "early" else "dallas",
                0 if case[0] == "window" else 20,
                1,
            ),
        )
    forecast = PopForecast(
        revision="synthetic-evaluator",
        catalog_fingerprint=catalog.fingerprint,
        status="ready",
        transitions=transitions,
    )
    state, advisories = evaluate_live(
        forecast,
        resolver.observation(),
        catalog=catalog,
        nearest_id="tokyo" if case[0] == "skipped" else "los-angeles",
        next_id=transitions[0].crossing.to_pop_id,
        now=base,
        state=PopLiveState(revision=forecast.revision),
    )
    return {
        "pop_forecast": forecast.model_dump(mode="json"),
        "pop_advisories": [item.model_dump(mode="json") for item in advisories],
        "pop_occurrences": [item.model_dump(mode="json") for item in state.occurrences],
    }


app = main.app
app.router.lifespan_context = fixture_lifespan


@app.post("/api/_synthetic/pop-evidence")
def set_case(body: dict):
    if body.get("case") not in {
        "tokyo",
        "geoip",
        "mapped-failure",
        "changed-failure",
        "stale",
        "window",
        "skipped",
        "mismatch",
        "early",
    }:
        raise HTTPException(422, "Unknown synthetic case")
    case[0] = body["case"]
    scenario_time[0] = datetime.now(timezone.utc)
    if case[0] == "stale":
        clock[0] += 31
    else:
        clock[0] += 901
        resolver.invalidate(clear_geolocation_cache=True)
        resolver.refresh(force=True)
    return {"case": case[0], "fixture": "synthetic dependency injection"}


@app.get("/api/_synthetic/pop-evidence.csv")
def export_csv():
    # Exercise the shipped timeline CSV exporter with an invented future segment.
    from app.mission.exporter.__main__ import _segment_rows

    start = datetime(2035, 1, 1, tzinfo=timezone.utc)
    timeline = MissionLegTimeline(
        mission_leg_id="synthetic-leg",
        segments=[
            TimelineSegment(
                id="synthetic-segment",
                start_time=start,
                end_time=start + timedelta(hours=1),
                status="nominal",
                x_state="available",
                ka_state="available",
                ku_state="available",
            )
        ],
        advisories=[],
        statistics={},
    )
    return Response(
        _segment_rows(timeline, None).to_csv(index=False), media_type="text/csv"
    )
