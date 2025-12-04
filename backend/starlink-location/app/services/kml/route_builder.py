"""Route construction from KML segments."""

import logging
from dataclasses import dataclass
from typing import Optional

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

    name: Optional[str]
    description: Optional[str]
    style: Optional[LineStyleInfo]
    coordinates: list[CoordinateTriple]
    altitude_mode: Optional[str]
    order: int


def build_primary_route(
    route_segments: list[RouteSegmentData],
    start_coord: Optional[CoordinateTriple],
    end_coord: Optional[CoordinateTriple],
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
    current: Optional[CoordinateTriple],
) -> tuple[Optional[int], bool]:
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
