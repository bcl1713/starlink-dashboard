"""Route construction from KML segments."""

import logging
from dataclasses import dataclass

from app.services.kml.geometry import (
    CoordinateTriple,
    LineStyleInfo,
    coordinates_match,
    deduplicate_coordinates,
)

logger = logging.getLogger(__name__)


@dataclass
class RouteSegmentData:
    """Represents a line segment placemark for the planned route."""

    name: str | None
    description: str | None
    style: LineStyleInfo | None
    coordinates: list[CoordinateTriple]
    altitude_mode: str | None
    order: int


def build_primary_route(
    route_segments: list[RouteSegmentData],
    start_coord: CoordinateTriple | None,
    end_coord: CoordinateTriple | None,
) -> list[CoordinateTriple]:
    """Construct the primary coordinate chain from the available segments.

    Args:
        route_segments: List of RouteSegmentData objects to chain
        start_coord: Optional starting coordinate to match
        end_coord: Optional ending coordinate to match

    Returns:
        List of chained CoordinateTriple objects representing primary route
    """
    # Filter segments to only include the main route (by color/style)
    filtered_segments = filter_segments_by_style(route_segments)

    segments_remaining = [seg for seg in filtered_segments if seg.coordinates]
    if not segments_remaining:
        return []

    path: list[CoordinateTriple] = []
    current = None

    if start_coord:
        path.append(start_coord)
        current = start_coord
    else:
        first_segment = segments_remaining.pop(0)
        path.extend(first_segment.coordinates)
        current = first_segment.coordinates[-1]

    safety_counter = 0
    max_iterations = len(segments_remaining) + 1

    while segments_remaining and safety_counter <= max_iterations:
        idx, reverse_needed = find_next_segment_index(segments_remaining, current)
        if idx is None:
            # Color-filtered segments don't connect properly. Return empty to
            # trigger legacy fallback, which will use all segments regardless of color
            logger.debug(
                "Color-filtered segments did not chain properly; "
                "%d segments remaining, current=%s",
                len(segments_remaining),
                (
                    f"({current.latitude:.6f},{current.longitude:.6f})"
                    if current
                    else "None"
                ),
            )
            return []

        segment = segments_remaining.pop(idx)
        coords_sequence = segment.coordinates
        if reverse_needed:
            coords_sequence = list(reversed(coords_sequence))

        if not path:
            path.extend(coords_sequence)
        else:
            path.extend(coords_sequence[1:])

        current = coords_sequence[-1]
        safety_counter += 1

        if end_coord and coordinates_match(current, end_coord):
            break

    deduped_path = deduplicate_coordinates(path)

    if len(deduped_path) < 2:
        return []

    return deduped_path


def filter_segments_by_style(
    segments: list[RouteSegmentData],
) -> list[RouteSegmentData]:
    """
    Filter route segments to only include the main route (exclude alternates).

    Flight planning software (like ForeFlight/RocketRoute) exports routes with:
    - Main route segments: color ffddad05 (orange/gold)
    - Alternate segments: color ffb3b3b3 (gray)

    This function filters to keep only the main route segments.

    Args:
        segments: All route segments extracted from KML file

    Returns:
        Filtered list containing only main route segments, or all segments if no color match
    """
    # Main route color from ForeFlight/RocketRoute export format
    main_route_color = "ffddad05"

    # Debug: log all colors found
    color_counts = {}
    for seg in segments:
        if seg.style and seg.style.color:
            color = seg.style.color.lower()
            color_counts[color] = color_counts.get(color, 0) + 1
        else:
            color_counts["(no color)"] = color_counts.get("(no color)", 0) + 1

    if color_counts:
        logger.debug("Segment colors: %s", color_counts)

    main_segments = [
        seg
        for seg in segments
        if seg.style
        and seg.style.color
        and seg.style.color.lower() == main_route_color.lower()
    ]

    if main_segments:
        logger.info(
            "Filtered segments by style: %d main route (ffddad05) from %d total",
            len(main_segments),
            len(segments),
        )
        return main_segments

    # Fallback: if no colored segments found, return all segments
    logger.warning(
        "No main route segments (ffddad05) found in %d segments; returning all",
        len(segments),
    )
    return segments


def find_next_segment_index(
    segments: list[RouteSegmentData],
    current: CoordinateTriple | None,
) -> tuple[int | None, bool]:
    """Locate the next segment that connects to the current coordinate.

    Args:
        segments: List of RouteSegmentData objects to search
        current: Current coordinate to match against segment endpoints

    Returns:
        Tuple of (segment_index, needs_reversal) where needs_reversal indicates
        if the segment coordinates should be reversed to maintain chain continuity
    """
    if current is None:
        return None, False

    for idx, segment in enumerate(segments):
        if not segment.coordinates:
            continue

        first = segment.coordinates[0]
        last = segment.coordinates[-1]

        if coordinates_match(first, current):
            return idx, False

        if coordinates_match(last, current):
            return idx, True

    return None, False


def flatten_route_segments(
    route_segments: list[RouteSegmentData],
) -> list[CoordinateTriple]:
    """Fallback: concatenate all segment coordinates in document order.

    Args:
        route_segments: List of RouteSegmentData objects to flatten

    Returns:
        List of all coordinates concatenated in document order with duplicates removed
    """
    combined: list[CoordinateTriple] = []

    for segment in sorted(route_segments, key=lambda seg: seg.order):
        if not combined:
            combined.extend(segment.coordinates)
        else:
            combined.extend(segment.coordinates)

    return deduplicate_coordinates(combined)


def build_planning_primary_route(route_segments, start_coord, end_coord, waypoints=()):
    """Preserve a complete ordered primary chain and occurrence provenance.

    A complete document-order chain is explicit visit evidence, including loops.
    Otherwise require a unique geometric chain; branches never flatten. Same-
    position/time aliases collapse, while source-timed dwell visits survive.
    """
    from app.services.kml.timing import extract_timestamp_from_description
    from app.services.kml.validator import KMLParseError

    if start_coord is None or end_coord is None:
        raise KMLParseError("Planning primary route requires endpoint waypoints")
    segments = [s for s in route_segments if s.coordinates]
    main = [
        s
        for s in segments
        if s.style and s.style.color and s.style.color.lower() == "ffddad05"
    ]
    if main:
        segments = main
    else:
        segments = [
            s
            for s in segments
            if not (s.style and s.style.color and s.style.color.lower() == "ffb3b3b3")
        ]
    ordered = []
    current = start_coord
    for segment in sorted(segments, key=lambda s: s.order):
        if coordinates_match(segment.coordinates[0], current):
            reverse = False
        elif coordinates_match(segment.coordinates[-1], current):
            reverse = True
        else:
            ordered = []
            break
        ordered.append((segment, reverse))
        current = segment.coordinates[0] if reverse else segment.coordinates[-1]
    if not ordered or not coordinates_match(current, end_coord):
        remaining = list(segments)
        ordered = []
        current = start_coord
        while remaining:
            candidates = []
            for i, segment in enumerate(remaining):
                if coordinates_match(segment.coordinates[0], current):
                    candidates.append((i, False))
                elif coordinates_match(segment.coordinates[-1], current):
                    candidates.append((i, True))
            if len(candidates) != 1:
                raise KMLParseError("Ambiguous or disconnected primary route chain")
            i, reverse = candidates[0]
            segment = remaining.pop(i)
            ordered.append((segment, reverse))
            current = segment.coordinates[0] if reverse else segment.coordinates[-1]
    path, provenance = [], []
    for segment, reverse in ordered:
        coords = list(reversed(segment.coordinates)) if reverse else segment.coordinates
        before = next((w for w in reversed(waypoints) if w.order < segment.order), None)
        after = next((w for w in waypoints if w.order > segment.order), None)
        before_time = (
            extract_timestamp_from_description(before.description) if before else None
        )
        after_time = (
            extract_timestamp_from_description(after.description) if after else None
        )
        dwell = (
            len(coords) == 2
            and coordinates_match(coords[0], coords[1])
            and before_time
            and after_time
            and before_time != after_time
            and before.coordinate
            and after.coordinate
            and coordinates_match(before.coordinate, coords[0])
            and coordinates_match(after.coordinate, coords[1])
        )
        for j, coord in enumerate(coords):
            if (
                path
                and coordinates_match(path[-1], coord, tolerance=1e-6)
                and not (dwell and j == 1)
            ):
                continue
            path.append(coord)
            provenance.append((segment.order, len(coords) - 1 - j if reverse else j))
    if len(path) < 2 or not coordinates_match(current, end_coord):
        raise KMLParseError("Primary route does not reach its expected arrival")
    return path, provenance
