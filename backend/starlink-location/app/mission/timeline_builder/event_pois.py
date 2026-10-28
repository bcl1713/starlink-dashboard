"""Resolve AR and manual outage boundaries into geographic map cues."""

from datetime import timedelta

from app.mission.poi_display import MISSION_POI_LABELS
from app.mission.timeline_builder.calculator import ensure_timezone
from app.mission.timeline_builder.utils import find_waypoint_coordinates


def route_position(projector, timestamp):
    """Return a position and route visit at an effective mission timestamp."""
    distance = projector.distance_for_timestamp(timestamp)
    sample = projector.sample_at_distance(distance)
    # A vertex belongs to its preceding segment, matching temporal sampling.
    segment = next(
        (
            i
            for i, end in enumerate(projector.cumulative_distances[1:])
            if distance <= end
        ),
        max(0, len(projector.route.points) - 2),
    )
    return sample.latitude, sample.longitude, segment


def create_ar_pois(create, mission, route, windows, projector, manual_tracks):
    """Use effective window timing and the same manual-track span as the timeline."""
    sources = {
        window.id or f"AAR-{index + 1}": window
        for index, window in enumerate(mission.transports.aar_windows)
    }
    for window in windows:
        source = sources.get(window.name)
        if source is None:
            continue
        use_timing = bool(
            source.start_anchor
            or source.end_anchor
            or source.override_start_time
            or source.override_end_time
            or source.override_start_elapsed
        )
        for boundary, timestamp, waypoint in (
            ("start", window.start_time, source.start_waypoint_name),
            ("end", window.end_time, source.end_waypoint_name),
        ):
            coordinates = (
                None if use_timing else find_waypoint_coordinates(route, waypoint)
            )
            segment = None
            if coordinates is None:
                lat, lon, segment = route_position(projector, timestamp)
                coordinates = (lat, lon)
            create(
                name=MISSION_POI_LABELS[f"aar_{boundary}"],
                latitude=coordinates[0],
                longitude=coordinates[1],
                icon="aar",
                kind=f"aar_{boundary}",
                expected_arrival_time=timestamp,
                route_segment_index=segment,
                description=f"AR window {boundary} ({waypoint})",
            )

    for track in manual_tracks:
        projections = [projector.project(p.latitude, p.longitude) for p in track.points]
        start = min(projections, key=lambda p: p.timestamp)
        end = max(projections, key=lambda p: p.timestamp)
        if end.timestamp <= start.timestamp:
            continue
        for boundary, projection in (("start", start), ("end", end)):
            _, _, segment = route_position(projector, projection.timestamp)
            create(
                name=MISSION_POI_LABELS[f"aar_{boundary}"],
                latitude=projection.latitude,
                longitude=projection.longitude,
                icon="aar",
                kind=f"aar_{boundary}",
                expected_arrival_time=projection.timestamp,
                route_segment_index=segment,
                description=f"Manual AR {boundary}: {track.name}",
            )


def create_outage_pois(create, outages, projector, prefix, label):
    """Merge overlapping outages so a map restore cue never occurs during a loss."""
    spans = sorted(
        (
            ensure_timezone(o.start_time),
            ensure_timezone(o.start_time) + timedelta(seconds=o.duration_seconds),
        )
        for o in outages
    )
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in merged:
        for boundary, timestamp in (("start", start), ("end", end)):
            if not projector.start_time <= timestamp <= projector.end_time:
                continue
            lat, lon, segment = route_position(projector, timestamp)
            create(
                name=MISSION_POI_LABELS[f"{prefix}_outage_{boundary}"],
                latitude=lat,
                longitude=lon,
                icon="satellite",
                kind=f"{prefix}_outage_{boundary}",
                expected_arrival_time=timestamp,
                route_segment_index=segment,
                description=f"{label} manual outage {boundary}",
            )
