"""Captured capability identity and clock checks for local status consumers."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from app.mission.pop_continuity import capabilities_from_timeline
from app.mission.pop_coverage_evidence import (
    coverage_snapshot,
    current_coverage_snapshot,
)
from app.mission.pop_forecast import mission_forecast_revision
from app.satellites.catalog import get_satellite_catalog
from app.satellites.rules import ConstraintConfig
from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


_CURRENT_COVERAGE = object()


def capability_input_revision(
    leg,
    route,
    constraint_config=None,
    satellite_catalog=None,
    *,
    ka_snapshot=_CURRENT_COVERAGE
):
    """Identify leg/config/geometry/timing inputs without rebuilding a mission."""
    catalog = satellite_catalog or get_satellite_catalog(read_only=True)
    if ka_snapshot is _CURRENT_COVERAGE:
        ka_snapshot = current_coverage_snapshot()
    return _digest(
        [
            ka_snapshot,
            leg.model_dump(
                mode="json",
                exclude={
                    "created_at",
                    "updated_at",
                    "is_active",
                    "name",
                    "description",
                    "notes",
                },
            ),
            route.model_dump(mode="json"),
            asdict(constraint_config or ConstraintConfig()),
            sorted(
                (s.satellite_id, s.transport, s.longitude) for s in catalog.list_all()
            ),
        ]
    )


def _capability_revision(spans):
    return _digest([s.model_dump(mode="json") for s in spans])


@dataclass(frozen=True)
class CapturedCallCapabilities:
    """Mission spans or evidence produced for one exact live forecast sample.

    A future live producer must publish live_eta evidence using the current
    route revision, catalog, forecast signature and sample UTC; it must evaluate
    fixed UTC constraints independently rather than shift planned intervals.
    """

    route_revision: str
    catalog_fingerprint: (
        str  # Capture provenance; PoP catalog does not constrain RF capability.
    )
    capability_revision: str
    spans: tuple[CapabilitySpan, ...]
    start_utc: datetime
    end_utc: datetime
    input_revision: str | None = None
    timing_basis: Literal["mission", "live_eta"] = "mission"
    forecast_signature: str | None = None
    sample_utc: datetime | None = None


def forecast_signature(forecast):
    return _digest(forecast.model_dump(mode="json"))


def capture_call_capabilities(timeline, route, projector):
    """Capture prepared evidence only when its route/timing/catalog still match."""
    forecast = timeline.pop_forecast
    if forecast is None or projector.route_snapshot != route.model_dump():
        raise ValueError("Missing or obsolete prepared capability inputs")
    # The stored revision includes route, mission UTC bounds, and catalog.
    from types import SimpleNamespace

    expected = mission_forecast_revision(
        route,
        projector,
        (
            SimpleNamespace(fingerprint=forecast.catalog_fingerprint)
            if forecast.catalog_fingerprint
            else None
        ),
    )
    if forecast.revision != expected:
        raise ValueError("Prepared forecast and capability timing revisions differ")
    spans = capabilities_from_timeline(timeline)
    return CapturedCallCapabilities(
        route_revision=_digest(route.model_dump(mode="json")),
        catalog_fingerprint=forecast.catalog_fingerprint,
        capability_revision=_capability_revision(spans),
        spans=spans,
        start_utc=projector.start_time,
        end_utc=projector.end_time,
        input_revision=timeline.call_capability_revision,
    )


def status_call_continuity(
    captured, forecast, route, *, now, flight_phase, projector, completed_ids
):
    """Reject stale/misaligned evidence; absence never means confirmed zero."""
    if captured is None or forecast.status not in ("ready", "disabled"):
        return None
    if captured.route_revision != _digest(
        route.model_dump(mode="json") if route else None
    ) or captured.capability_revision != _capability_revision(captured.spans):
        return None
    if captured.timing_basis == "mission":
        if projector is None and flight_phase == "pre_departure":
            from app.mission.timeline_builder.calculator import (
                RouteTemporalProjector,
                derive_mission_window,
            )

            start, end = derive_mission_window(route)
            projector = RouteTemporalProjector(route, start, end)
        if (
            projector is None
            or projector.route_snapshot != route.model_dump()
            or (projector.start_time, projector.end_time)
            != (captured.start_utc, captured.end_utc)
        ):
            return None
    elif (
        captured.sample_utc != now
        or captured.forecast_signature != forecast_signature(forecast)
    ):
        return None
    start = (
        captured.start_utc
        if flight_phase == "pre_departure"
        else max(now, captured.start_utc)
    )
    if start >= captured.end_utc:
        return None
    remaining = forecast.model_copy(
        update={
            "transitions": tuple(
                t for t in forecast.transitions if t.crossing.id not in completed_ids
            )
        }
    )
    return project_call_continuity(
        remaining, captured.spans, start_utc=start, end_utc=captured.end_utc
    )


def saved_call_capabilities(leg, parent_id, route):
    """Read an already prepared local timeline; never evaluate capability per poll."""
    from app.mission.storage import load_mission_timeline
    from app.mission.timeline_builder.calculator import (
        RouteTemporalProjector,
        derive_mission_window,
    )

    timeline = load_mission_timeline(leg.id, parent_id)
    if timeline is None:
        return None
    evidence = timeline.statistics.get("_call_capability_evidence", {})
    current = current_coverage_snapshot()
    if (
        current is None
        or evidence.get("ka_source")
        not in ("default_file", "application_cache", "planning_snapshot", "missing")
        or evidence.get("ka_snapshot") != current
        or timeline.call_capability_revision
        != capability_input_revision(leg, route, ka_snapshot=current)
    ):
        return None
    start, end = derive_mission_window(route)
    return capture_call_capabilities(
        timeline, route, RouteTemporalProjector(route, start, end)
    )


def capture_source_evidence(
    mission,
    samples,
    assignments,
    coverage_sampler,
    planning_evaluation,
    satellite_catalog,
    coverage_source,
):
    """Do not equate default available transport states with measured capability.

    Catalog geometry is revision checked at reuse. POI-only geometry currently
    has no captured identity, so it cannot certify future X availability.
    """
    catalog = satellite_catalog or get_satellite_catalog(read_only=True)
    assigned = {mission.transports.initial_x_satellite_id, *(a[1] for a in assignments)}
    known = (
        bool(assigned)
        and None not in assigned
        and all(
            catalog.get_satellite(sid) is not None
            and catalog.get_satellite(sid).longitude is not None
            for sid in assigned
        )
    )
    from datetime import timedelta

    snapshot = coverage_snapshot(coverage_sampler)
    return {
        "ka": snapshot["valid"],
        "ka_snapshot": snapshot,
        "ka_source": coverage_source,
        "ka_manual_outages": [
            {
                "id": outage.id,
                "start_utc": outage.start_time.isoformat(),
                "end_utc": (
                    outage.start_time + timedelta(seconds=outage.duration_seconds)
                ).isoformat(),
            }
            for outage in mission.transports.ka_outages
        ],
        "x": planning_evaluation is not None
        or (known and all(s.heading is not None for s in samples)),
        "starshield_enabled": mission.transports.starshield_enabled is not False,
    }
