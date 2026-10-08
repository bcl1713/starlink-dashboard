"""One immutable, read-only export revision shared by every consumer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import pairwise
from typing import Literal

from app.mission.derived_route import (
    build_derived_route_estimate,
    derived_route_for_estimate,
)
from app.mission.models import Mission, MissionLegTimeline
from app.mission.timeline_builder.aar import resolve_aar_windows
from app.mission.timeline_builder.calculator import (
    derive_mission_window,
    route_with_adjusted_departure,
)
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.poi import POI
from app.satellites.rules import ConstraintConfig, EventType
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

from .snapshot_inputs import (
    SnapshotCaptureError,
    SourcePayload,
    canonical_json,
    capture_inputs,
    captured_coverage,
)
from .snapshot_views import RouteView, captured_catalog, captured_pois, source_content

# Keep provenance public alongside the DTO for callers and successor tasks.
__all__ = [
    "ExportSnapshot",
    "LegSnapshot",
    "SnapshotCaptureError",
    "capture_export_snapshot",
]


@dataclass(frozen=True)
class LegSnapshot:
    leg_id: str
    leg_json: bytes
    effective_route_json: bytes | None
    timeline_json: bytes | None
    source_records: tuple[bytes, ...]
    resolved_restrictions: tuple[bytes, ...]
    utc_bounds: tuple[datetime, datetime] | None
    preparation_origin: Literal["rebuilt", "cached", "missing"]
    warnings: tuple[str, ...]
    map_pois: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class ExportSnapshot:
    mission_id: str
    fingerprint: str
    metadata_json: bytes
    legs: tuple[LegSnapshot, ...]
    source_payloads: tuple[SourcePayload, ...]
    warnings: tuple[str, ...]


def _availability_basis(
    artifacts, sampler, catalog, pois, sources
) -> tuple[bytes, ...]:
    """Capture prerequisite facts omitted by the legacy default-state reducer.

    These export-only records do not change prepared events, timeline segments
    or any legacy consumer. Missing geometry/coverage must remain detectable by
    a pure LegSnapshot consumer after live managers have changed.
    """
    start, end = artifacts.projector.start_time, artifacts.projector.end_time
    revision = sha256(
        canonical_json([(source.name, source.digest) for source in sources])
    ).hexdigest()
    records = []

    def record(transport, a, b, available, **metadata):
        raw = {
            "source_type": "availability_basis",
            "transport": transport,
            "start_time": a,
            "end_time": b,
            "state": "available",
            "metadata": {"prerequisites_available": available, **metadata},
            "source_revision": revision,
        }
        raw["source_id"] = (
            "derived:availability-basis:" + sha256(canonical_json(raw)).hexdigest()[:20]
        )
        records.append(canonical_json(raw))

    record(
        "Ka",
        start,
        end,
        sampler is not None and bool(artifacts.timeline.coverage_events),
    )
    # Ku is normally always-on in the domain model, subject to saved overrides.
    record("Ku", start, end, True)
    points = artifacts.route.points
    heading_available = any(
        (a.latitude, a.longitude) != (b.latitude, b.longitude)
        for a, b in pairwise(points)
    )
    assignments = artifacts.x_assignments or ((start, "", None),)
    for index, (a, satellite_id, transition_id) in enumerate(assignments):
        b = assignments[index + 1][0] if index + 1 < len(assignments) else end
        if max(a, start) >= min(b, end):
            continue
        satellite = catalog.get_satellite(satellite_id)
        longitude = satellite.longitude if satellite else None
        if longitude is None:
            poi = pois.find_global_poi_by_name(satellite_id)
            longitude = poi.longitude if poi else None
        record(
            "X",
            max(a, start),
            min(b, end),
            bool(satellite_id) and longitude is not None and heading_available,
            satellite_id=satellite_id,
            transition_id=transition_id,
            heading_available=heading_available,
        )
    return tuple(records)


def _event_sources(artifacts, config: ConstraintConfig) -> tuple[bytes, ...]:
    """Restore saved transition identity omitted by the legacy event producer."""
    records = []
    buffer = timedelta(minutes=config.transition_buffer_minutes)
    for event in artifacts.events:
        raw = asdict(event)
        if event.event_type in {
            EventType.X_TRANSITION_START,
            EventType.X_TRANSITION_END,
        }:
            midpoint = event.timestamp + (
                buffer if event.event_type == EventType.X_TRANSITION_START else -buffer
            )
            identities = [
                identity
                for timestamp, satellite, identity in artifacts.x_assignments
                if identity
                and timestamp == midpoint
                and satellite == event.satellite_id
            ]
            if len(identities) == 1:
                raw["metadata"]["transition_id"] = identities[0]
        records.append(canonical_json(raw))
    return tuple(records)


def _sof_records(start, end, config: ConstraintConfig) -> list[dict]:
    return [
        {
            "source_id": "sof-takeoff",
            "kind": "sof",
            "label": "Safety-of-Flight (takeoff)",
            "start_time": start,
            "end_time": min(
                end, start + timedelta(minutes=config.takeoff_buffer_minutes)
            ),
        },
        {
            "source_id": "sof-landing",
            "kind": "sof",
            "label": "Safety-of-Flight (landing)",
            "start_time": max(
                start, end - timedelta(minutes=config.landing_buffer_minutes)
            ),
            "end_time": end,
        },
    ]


def _restrictions(leg, artifacts, config: ConstraintConfig) -> tuple[bytes, ...]:
    start, end = artifacts.projector.start_time, artifacts.projector.end_time
    records = _sof_records(start, end, config)
    resolved = {
        w.name: w
        for w in resolve_aar_windows(leg, artifacts.route, artifacts.projector)
    }
    for index, window in enumerate(leg.transports.aar_windows):
        identity = window.id or f"AAR-{index + 1}"
        period = resolved.get(identity)
        records.append(
            {
                "source_id": identity,
                "kind": "ar",
                "label": identity,
                "start_time": period.start_time if period else None,
                "end_time": period.end_time if period else None,
            }
        )
    ends = {
        e.metadata.get("track_id"): e.timestamp
        for e in artifacts.events
        if e.event_type == EventType.MANUAL_AAR_TRACK_END
    }
    for event in artifacts.events:
        if event.event_type == EventType.MANUAL_AAR_TRACK_START:
            identity = event.metadata["track_id"]
            records.append(
                {
                    "source_id": identity,
                    "kind": "manual_ar",
                    "label": event.metadata["track_name"],
                    "start_time": event.timestamp,
                    "end_time": ends.get(identity),
                }
            )
    return tuple(canonical_json(record) for record in records)


def capture_export_snapshot(
    mission_id: str,
    route_manager: RouteManager,
    poi_manager: POIManager,
) -> ExportSnapshot:
    """Copy under capture locks, release, then prepare each leg exactly once."""
    metadata, sources, warnings = capture_inputs(mission_id, route_manager, poi_manager)
    mission = Mission.model_validate_json(metadata)
    routes, pois = RouteView(sources), captured_pois(sources)
    catalog = captured_catalog(sources)
    config = ConstraintConfig(**json.loads(source_content(sources, "constraints")))
    try:
        sampler = captured_coverage(sources)
        coverage_error = None
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        sampler, coverage_error = None, type(exc).__name__
    legs = []
    for leg in mission.legs:
        leg_json = canonical_json(leg.model_dump(mode="json"))
        notes = []
        timeline, effective_route, bounds = None, None, None
        events, restrictions, map_pois = (), (), ()
        origin = "missing"
        try:
            if coverage_error:
                raise ValueError(f"Captured coverage unavailable: {coverage_error}")
            artifacts = prepare_mission_timeline(
                leg.model_copy(deep=True),
                routes,
                pois,
                coverage_sampler=sampler,
                parent_mission_id=mission.id,
                discover_coverage=False,
                satellite_catalog=catalog,
                constraint_config=config,
            )
            timeline, effective_route = artifacts.timeline, artifacts.route
            bounds = (
                artifacts.projector.start_time.astimezone(timezone.utc),
                artifacts.projector.end_time.astimezone(timezone.utc),
            )
            events = _event_sources(artifacts, config)
            events += _availability_basis(artifacts, sampler, catalog, pois, sources)
            restrictions = _restrictions(leg, artifacts, config)
            # The map only reads names/coordinates; prepared markers need no
            # publication, persistent IDs, or storage-side projection.
            map_pois = tuple(
                canonical_json(
                    POI(
                        **poi.model_dump(mode="json"),
                        id=f"export-{leg.id}-{index}",
                        generated_source="mission-timeline",
                    ).model_dump(mode="json")
                )
                for index, poi in enumerate(artifacts.generated_pois)
            )
            origin = "rebuilt"
        except (
            RuntimeError,
            ValueError,
            OSError,
            KeyError,
            TypeError,
            AttributeError,
            LookupError,
            ConnectionError,
            TimeoutError,
            ImportError,
            EOFError,
        ) as exc:
            timeline, effective_route, bounds = None, None, None
            events, restrictions, map_pois = (), (), ()
            cached = source_content(sources, f"cache/{leg.id}")
            if cached != b"null" and "cache_error" not in json.loads(cached):
                timeline = MissionLegTimeline.model_validate_json(cached)
                origin = "cached"
                notes.append(
                    f"Leg {leg.id}: rebuild unavailable ({type(exc).__name__}); cached timeline retains its original prediction basis."
                )
            else:
                notes.append(
                    f"Leg {leg.id}: rebuild unavailable ({type(exc).__name__}); timeline data missing."
                )
            # Current planned bounds are independent of stale cached predictions.
            route = routes.get_route(leg.route_id) if leg.route_id else None
            if route:
                effective_route = route_with_adjusted_departure(
                    route, leg.adjusted_departure_time
                )
                splice = leg.transports.manual_route_splice
                track = next(
                    (
                        track
                        for track in leg.transports.manual_aar_tracks
                        if splice and track.id == splice.enabled_track_id
                    ),
                    None,
                )
                if track:
                    estimate = build_derived_route_estimate(
                        effective_route, track, splice
                    )
                    effective_route = derived_route_for_estimate(
                        effective_route, estimate
                    )
                    if not estimate.available:
                        notes.append(
                            f"Leg {leg.id}: selected splice unavailable; planned route retained."
                        )
                elif splice:
                    notes.append(
                        f"Leg {leg.id}: selected splice track missing; planned route retained."
                    )
                try:
                    bounds = tuple(
                        t.astimezone(timezone.utc)
                        for t in derive_mission_window(effective_route)
                    )
                except (ValueError, RuntimeError):
                    effective_route = None
            if bounds:
                restrictions = tuple(
                    canonical_json(r) for r in _sof_records(*bounds, config)
                )
            notes.append(
                f"Leg {leg.id}: canonical events and resolved AR restrictions unavailable."
            )
        if effective_route is None:
            notes.append(f"Leg {leg.id}: effective route data missing.")
        legs.append(
            LegSnapshot(
                leg.id,
                leg_json,
                (
                    canonical_json(effective_route.model_dump(mode="json"))
                    if effective_route
                    else None
                ),
                canonical_json(timeline.model_dump(mode="json")) if timeline else None,
                events,
                restrictions,
                bounds,
                origin,
                tuple(notes),
                map_pois,
            )
        )
    digest = sha256(metadata)
    for source in sources:
        digest.update(canonical_json([source.name, source.digest]))
    all_warnings = warnings + tuple(note for leg in legs for note in leg.warnings)
    return ExportSnapshot(
        mission.id, digest.hexdigest(), metadata, tuple(legs), sources, all_warnings
    )
