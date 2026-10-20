"""Content identity and prerequisite evidence for the evaluated Ka snapshot."""

import hashlib
import json
from datetime import datetime
from math import isfinite
from pathlib import Path

from app.satellites.coverage import CoverageSampler


def coverage_snapshot(sampler):
    """Hash both captured GeoJSON and the actual indexed polygons used by queries."""
    data = getattr(sampler, "coverage_data", None)
    polygons = getattr(sampler, "satellite_polygons", {})
    valid = (
        isinstance(data, dict)
        and data.get("type") == "FeatureCollection"
        and bool(polygons)
    )
    try:
        valid = (
            valid
            and all(bool(rings) for rings in polygons.values())
            and all(
                len(ring) >= 3
                and all(
                    isfinite(lon)
                    and isfinite(lat)
                    and -180 <= lon <= 180
                    and -90 <= lat <= 90
                    for lon, lat in ring
                )
                for rings in polygons.values()
                for ring in rings
            )
        )
        content = json.dumps(
            {"data": data, "polygons": polygons}, sort_keys=True, allow_nan=False
        )
    except (TypeError, ValueError, AttributeError):
        return {"digest": None, "valid": False}
    return {
        "digest": hashlib.sha256(content.encode()).hexdigest(),
        "valid": bool(valid),
    }


def current_coverage_snapshot():
    """Verify the application's current cache agrees with the current disk source.

    A stale/mutated cache cannot stamp old capabilities with the new file's
    identity. Missing or broken inputs remain unknown evidence, not a gap.
    """
    from app.mission import timeline_service

    path = Path("data/sat_coverage/commka.geojson")
    try:
        disk = coverage_snapshot(CoverageSampler(path) if path.exists() else None)
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    cache = timeline_service._COVERAGE_SAMPLER
    if cache is not None and coverage_snapshot(cache) != disk:
        return None
    return disk


def coverage_source_kind(sampler, *, injected=False, planning=False):
    if planning:
        return "planning_snapshot"
    if sampler is None:
        return "missing"
    if not injected:
        return "default_file"
    from app.mission import timeline_service

    return (
        "application_cache"
        if sampler is timeline_service._COVERAGE_SAMPLER
        else "custom"
    )


def manual_ka_unavailable(segment, evidence):
    """Only explicit manual outage bounds can override failed coverage evidence."""
    for outage in evidence.get("ka_manual_outages", ()):
        try:
            start = datetime.fromisoformat(outage["start_utc"])
            end = datetime.fromisoformat(outage["end_utc"])
            if start <= segment.start_time and segment.end_time <= end:
                return True
        except (ValueError, TypeError, KeyError):
            continue
    return False
