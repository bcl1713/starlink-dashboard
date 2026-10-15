"""Read-only canonical grouping of normalized reported SIGMET evidence."""

import copy
import hashlib
import json
from dataclasses import dataclass

SEMANTIC_FIELDS = (
    "issued_at_ms",
    "revision",
    "phenomenon",
    "severity",
    "valid_from_ms",
    "valid_to_ms",
    "vertical",
    "amends",
    "cancelled",
    "cancellation_target",
)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def notice_key(context_key: str, bulletin_key: str, semantic_digest: str) -> str:
    return digest(
        ["route-sigmet-notice-v1", context_key, bulletin_key, semantic_digest]
    )


def _ring(points):
    values = [
        tuple(0.0 if number == 0 else float(number) for number in point)
        for point in points
    ]
    if values and values[0] == values[-1]:
        values.pop()
    if not values:
        return ()
    # Booth's minimum rotation keeps repeated vertices linear in time/space.
    return min(_rotation(values), _rotation(list(reversed(values))))


def _rotation(values):
    doubled = values + values
    length = len(values)
    left, right, offset = 0, 1, 0
    while left < length and right < length and offset < length:
        a, b = doubled[left + offset], doubled[right + offset]
        if a == b:
            offset += 1
            continue
        if a > b:
            left = left + offset + 1
            if left <= right:
                left = right + 1
        else:
            right = right + offset + 1
            if right <= left:
                right = left + 1
        offset = 0
    start = min(left, right)
    return tuple(doubled[start : start + length])


def _polygon(rings):
    if not rings:
        return ()
    return (_ring(rings[0]), tuple(sorted(_ring(hole) for hole in rings[1:])))


def _geometry(geometry):
    if geometry is None:
        return None
    if geometry["type"] == "Polygon":
        polygons = [_polygon(geometry["coordinates"])]
    elif geometry["type"] == "MultiPolygon":
        polygons = [_polygon(polygon) for polygon in geometry["coordinates"]]
    else:
        raise ValueError("Expected normalized polygon geometry")
    return tuple(sorted(polygons))


def _semantic(properties):
    return {
        **{field: properties.get(field) for field in SEMANTIC_FIELDS},
        "raw_text": " ".join(properties.get("raw_text", "").split()),
    }


@dataclass(frozen=True)
class BulletinGroup:
    bulletin_key: str
    semantic_digest: str
    feature_ids: list[str]
    properties: dict
    geometries: list[dict]
    identity_uncertain: bool
    valid_from_ms: int
    expires_at_ms: int

    def notice_key(self, context_key: str) -> str:
        return notice_key(context_key, self.bulletin_key, self.semantic_digest)


def _replaces(new: dict, old: dict) -> bool:
    """Only a verified explicit relation can retire a competing revision."""
    relation = "/".join(new[field] for field in ("issuer", "fir", "bulletin_series"))
    return (
        not new.get("cancelled")
        and not old.get("cancelled")
        and new.get("amends") == relation
        and new.get("issued_at_ms") is not None
        and old.get("issued_at_ms") is not None
        and new["issued_at_ms"] > old["issued_at_ms"]
    )


def group_bulletins(features: list[dict]) -> list[BulletinGroup]:
    """Retain cancellation evidence; callers apply actual-UTC eligibility later.

    Geometry variants share one semantic group. Unattributed competing revisions
    use content-derived identities and remain explicitly uncertain. Returned
    evidence is detached from the shared normalized input.
    """
    buckets = {}
    for feature in features:
        properties = feature["properties"]
        semantic = _semantic(properties)
        uncertain = not all(
            properties.get(key) for key in ("issuer", "fir", "bulletin_series")
        )
        identity = [
            properties.get(key)
            for key in (
                "issuer",
                "fir",
                "bulletin_series",
                "valid_from_ms",
                "valid_to_ms",
            )
        ]
        base = digest(
            ["sigmet-bulletin-v1", identity if not uncertain else [identity, semantic]]
        )
        bucket = buckets.setdefault(base, {"uncertain": uncertain, "variants": {}})
        variant = bucket["variants"].setdefault(
            digest(semantic),
            {"semantic": semantic, "properties": properties, "features": []},
        )
        variant["features"].append(feature)

    groups = []
    for base, bucket in buckets.items():
        variants = list(bucket["variants"].values())
        if not bucket["uncertain"]:
            variants = [
                old
                for old in variants
                if not any(
                    _replaces(new["properties"], old["properties"])
                    for new in variants
                    if new is not old
                )
            ]
        competing = len(variants) > 1
        for variant in variants:
            properties = variant["properties"]
            geometries = {}
            for feature in variant["features"]:
                canonical = _geometry(feature.get("geometry"))
                if canonical is not None:
                    geometries.setdefault(digest(canonical), feature["geometry"])
            semantic_digest = digest(
                ["sigmet-semantic-v1", variant["semantic"], sorted(geometries)]
            )
            key = (
                digest(["sigmet-unresolved-v1", base, semantic_digest])
                if competing
                else base
            )
            groups.append(
                BulletinGroup(
                    bulletin_key=key,
                    semantic_digest=semantic_digest,
                    feature_ids=sorted(
                        {feature["id"] for feature in variant["features"]}
                    ),
                    properties=copy.deepcopy(properties),
                    geometries=[
                        copy.deepcopy(geometries[key]) for key in sorted(geometries)
                    ],
                    identity_uncertain=bucket["uncertain"] or competing,
                    valid_from_ms=properties["valid_from_ms"],
                    expires_at_ms=properties["expires_at_ms"],
                )
            )
    return sorted(groups, key=lambda group: (group.bulletin_key, group.semantic_digest))
