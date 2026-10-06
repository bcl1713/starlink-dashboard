"""Offline international SIGMET proof; incomplete coverage never means clear.

Only explicit raw-bulletin SFC/FL or FL/FL intervals establish vertical tags.
Provider numeric base/top fields have unknown units/reference in AWC's schema.
Topology uses planar degrees solely to split a polygon at the longitude seam;
it makes no geodesic area or operational aviation-safety claim.
"""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

from shapely.affinity import translate
from shapely.geometry import Polygon, MultiPolygon, box, mapping
from shapely.errors import GEOSException

from .grid import canonical, publish_payloads
from .model import CaptureManifest, ProductArtifact, capture_manifest_path, file_hash, object_path

MAX_ADVISORIES = 500
MAX_VERTICES = 100_000
NORMALIZATION_VERSION = "diagnostic-advisory-v1"


def _instant(value):
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(instant.timestamp() * 1000) if instant.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _vertical(properties, raw):
    result = {"status": "unknown", "base": None, "top": None, "evidence": None,
              "provider_numeric": {"base": properties.get("base"), "top": properties.get("top"), "units": "unknown", "reference": "unknown"}}
    # Narrow syntax: do not infer provider-wide numeric units or reinterpret
    # height/MSL/AGL/plain FT as standard-pressure flight levels.
    matches = list(re.finditer(r"\b(SFC|FL\d{2,3})\s*/\s*(FL\d{2,3})\b", raw))
    if len(matches) != 1:
        return result
    match = matches[0]
    def tag(token):
        if token == "SFC":
            return {"kind": "surface", "value": 0, "units": "surface", "reference": "surface"}
        return {"kind": "flight-level", "value": int(token[2:]), "units": "hundreds-ft", "reference": "standard-pressure"}
    base, top = tag(match[1]), tag(match[2])
    if base["value"] > top["value"]:
        return result
    result.update(status="known", base=base, top=top, evidence={"source": "raw-bulletin", "text": match[0]})
    return result


def _unwrap_ring(ring):
    if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("polygon ring must be closed")
    output = []
    for position in ring:
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            raise ValueError("unsupported polygon position")
        lon, lat = position
        if (type(lon) not in (int, float) or type(lat) not in (int, float)
                or not math.isfinite(lon) or not math.isfinite(lat)
                or not -180 <= lon <= 180 or not -90 <= lat <= 90):
            raise ValueError("invalid geographic coordinate")
        if output:
            while lon - output[-1][0] > 180:
                lon -= 360
            while lon - output[-1][0] < -180:
                lon += 360
        output.append((lon, lat))
    if output[0] != output[-1] or max(p[0] for p in output) - min(p[0] for p in output) >= 360:
        raise ValueError("ambiguous globe-winding ring")
    return output


def _polygons(geometry):
    if geometry is None or not isinstance(geometry, dict):
        raise ValueError("unlocated source")
    if geometry.get("type") == "Polygon":
        polygons = [geometry.get("coordinates")]
    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry.get("coordinates")
    else:
        raise ValueError("unsupported source geometry")
    if not isinstance(polygons, list) or not polygons:
        raise ValueError("empty polygon")
    return polygons


def _split_geometry(geometry, vertex_budget):
    polygons = _polygons(geometry)
    if any(not isinstance(p, list) or not p or any(not isinstance(r, list) for r in p) for p in polygons):
        raise ValueError("invalid polygon coordinates")
    source_vertices = sum(len(r) for p in polygons for r in p)
    if source_vertices > vertex_budget:
        raise ValueError("vertex budget exhausted")
    source, pieces = [], []
    for rings in polygons:
        exterior = _unwrap_ring(rings[0])
        center = (min(p[0] for p in exterior) + max(p[0] for p in exterior)) / 2
        holes = []
        for ring in rings[1:]:
            hole = _unwrap_ring(ring)
            hole_center = (min(p[0] for p in hole) + max(p[0] for p in hole)) / 2
            shift = 360 * round((center - hole_center) / 360)
            holes.append([(lon + shift, lat) for lon, lat in hole])
        polygon = Polygon(exterior, holes)
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError("invalid source polygon")
        source.append(polygon)
        first = math.floor((polygon.bounds[0] + 180) / 360)
        last = math.floor((polygon.bounds[2] + 180) / 360)
        for strip in range(first, last + 1):
            clipped = polygon.intersection(box(-180 + strip * 360, -90, 180 + strip * 360, 90))
            parts = [clipped] if clipped.geom_type == "Polygon" else list(clipped.geoms) if clipped.geom_type in ("MultiPolygon", "GeometryCollection") else []
            for part in parts:
                if part.geom_type == "Polygon" and not part.is_empty and part.area > 0:
                    pieces.append(translate(part, xoff=-360 * strip))
    # Reject overlap/malformed multipolygon; do not silently repair the input.
    if not MultiPolygon(source).is_valid or not pieces:
        raise ValueError("invalid source multipolygon")
    output = pieces[0] if len(pieces) == 1 else MultiPolygon(pieces)
    if not output.is_valid or not math.isclose(sum(p.area for p in source), output.area, rel_tol=1e-10, abs_tol=1e-9):
        raise ValueError("split polygon area/topology changed")
    count = sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors) for p in pieces)
    if count > vertex_budget:
        raise ValueError("split vertex budget exhausted")
    return mapping(output), count


def normalize_advisories(capture: CaptureManifest, destination: Path) -> ProductArtifact:
    """Normalize at the immutable capture instant; retain all bounded audit text.

    advisories.geojson contains only active located polygons at captured_at_ms.
    records.geojson preserves inactive/unlocated records for diagnostic lineage.
    Consumers must recheck real UTC [start,end) validity unless explicitly replaying
    the declared captured instant. Unknown coverage and altitude remain unknown.
    """
    if capture.source != "isigmet" or len(capture.objects) != 1:
        raise ValueError("one international SIGMET source object required")
    receipt = capture_manifest_path(capture)
    source_path = object_path(capture, capture.objects[0])
    try:
        collection = json.loads(source_path.read_bytes())
    except (ValueError, UnicodeError) as error:
        raise ValueError("invalid/truncated advisory JSON") from error
    if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection" or not isinstance(collection.get("features"), list):
        raise ValueError("source must be a GeoJSON FeatureCollection")
    features = collection["features"]
    reasons = ["provider-scope-and-result-cap-unverified"]
    incomplete = False
    if collection.get("truncated") is True or collection.get("hasMore") is True or collection.get("next"):
        incomplete = True
        reasons.append("provider-declared-truncation")
    if len(features) > MAX_ADVISORIES:
        incomplete = True
        reasons.append("diagnostic-advisory-cap")
    # The documented generic API cap is 400, not a proven isigmet-specific cap.
    if len(features) >= 400:
        reasons.append("generic-api-cap-may-apply")
    records, used_vertices = [], 0
    for index, feature in enumerate(features[:MAX_ADVISORIES]):
        if not isinstance(feature, dict) or feature.get("type") != "Feature" or not isinstance(feature.get("properties"), dict):
            incomplete = True
            reasons.append("malformed-feature")
            continue
        properties = feature["properties"]
        raw = properties.get("rawSigmet")
        raw = raw if isinstance(raw, str) else ""
        start, end = _instant(properties.get("validTimeFrom")), _instant(properties.get("validTimeTo"))
        cancelled = bool(re.search(r"\b(?:CNL|CANCELLED|CANCELED)\b", raw, re.I))
        interval_known = start is not None and end is not None and start < end
        status = "cancelled" if cancelled else "unknown-validity" if not interval_known else "future" if capture.captured_at_ms < start else "expired" if capture.captured_at_ms >= end else "active"
        geometry, location_error = None, None
        try:
            geometry, count = _split_geometry(feature.get("geometry"), MAX_VERTICES - used_vertices)
            used_vertices += count
        except (ValueError, TypeError, GEOSException) as error:
            location_error = str(error)
            if "budget" in location_error:
                incomplete = True
                reasons.append("diagnostic-vertex-cap")
        lineage_hash = hashlib.sha256(canonical(feature)).hexdigest()
        record = {"type": "Feature", "id": lineage_hash, "geometry": geometry, "properties": {
            "issuer": properties.get("icaoId"), "fir_id": properties.get("firId"), "fir_name": properties.get("firName"),
            "series_id": properties.get("seriesId"), "hazard": properties.get("hazard"), "qualifier": properties.get("qualifier"),
            "raw_text": raw, "validity": {"start_ms": start, "end_ms": end, "interval": "[start,end)"},
            "vertical": _vertical(properties, raw), "cancellation": {"cancelled": cancelled, "evidence": "raw-bulletin" if cancelled else None},
            "revision": {"status": "declared" if re.search(r"\b(?:AMD|COR)\b", raw) else "unverified", "source_feature_sha256": lineage_hash},
            "source_index": index, "source_sha256": capture.objects[0].sha256, "status": status,
            "location_status": "located" if geometry is not None else "unlocated", "location_error": location_error,
        }}
        records.append(record)
    # A currently valid cancellation for the same issuer/FIR/series suppresses
    # an earlier record, even if the provider also retained its original polygon.
    groups = {}
    for record in records:
        p = record["properties"]
        key = (p["issuer"], p["fir_id"], p["series_id"])
        if all(isinstance(item, str) and item for item in key):
            groups.setdefault(key, []).append(record)
    for group in groups.values():
        cancellations = [r for r in group if r["properties"]["cancellation"]["cancelled"]]
        for record in group:
            p = record["properties"]
            if p["status"] == "active" and any(c["properties"]["validity"]["start_ms"] is not None and c["properties"]["validity"]["end_ms"] is not None and c["properties"]["validity"]["start_ms"] <= capture.captured_at_ms < c["properties"]["validity"]["end_ms"] for c in cancellations):
                p["status"] = "cancelled-by-series"
    active = [r for r in records if r["properties"]["status"] == "active" and r["geometry"] is not None]
    payloads = {"advisories.geojson": canonical({"type": "FeatureCollection", "features": active}) + b"\n", "records.geojson": canonical({"type": "FeatureCollection", "features": records}) + b"\n"}
    machine = {"schema": "aviation-weather-v1", "representation": "advisory-v1", "source_id": "isigmet", "normalization_version": NORMALIZATION_VERSION}
    product_id = hashlib.sha256(canonical(machine)).hexdigest()
    descriptor = {**machine, "product_id": product_id, "instance_id": hashlib.sha256(canonical({"product_id": product_id, "source_sha256": capture.objects[0].sha256, "captured_at_ms": capture.captured_at_ms})).hexdigest(),
        "capture_manifest_sha256": file_hash(receipt), "captured_at_ms": capture.captured_at_ms, "diagnostic_replay_at_ms": capture.captured_at_ms,
        "active_selection": {"at_ms": capture.captured_at_ms, "interval": "[start,end)", "require_utc_recheck": True},
        "attribution": list(capture.attribution), "source_objects": [{"url": o.url, "sha256": o.sha256, "byte_size": o.byte_size} for o in capture.objects],
        "coverage": {"scope": "provider-returned-international-sigmet-snapshot", "completeness": "incomplete" if incomplete else "unverified", "worldwide_clear": False, "reasons": sorted(set(reasons)), "provider_result_cap": "unverified; most AWC endpoints documented at 400"},
        "counts": {"source": len(features), "retained": len(records), "active_located": len(active), "unlocated": sum(r["geometry"] is None for r in records), "vertices": used_vertices},
        "limits": {"advisories": MAX_ADVISORIES, "vertices": MAX_VERTICES},
    }
    for key, filename in (("advisories", "advisories.geojson"), ("records", "records.geojson")):
        payload = payloads[filename]
        descriptor[key] = {"path": filename, "sha256": hashlib.sha256(payload).hexdigest(), "byte_size": len(payload), "format": "geojson"}
    return publish_payloads(descriptor, payloads, receipt, destination)
