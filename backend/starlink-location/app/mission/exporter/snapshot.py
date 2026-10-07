"""One immutable, read-only export revision shared by every consumer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
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


def _restrictions(leg, artifacts, config: ConstraintConfig) -> tuple[bytes, ...]:
    start, end = artifacts.projector.start_time, artifacts.projector.end_time
    records = [
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
            events = tuple(canonical_json(asdict(event)) for event in artifacts.events)
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
            notes.append(
                f"Leg {leg.id}: canonical events and resolved restrictions unavailable."
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
