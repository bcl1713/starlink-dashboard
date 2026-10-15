"""Validate actual GFS listings and exact instant-field inventories."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from app.models.aviation_grid import HORIZONS, RangeRef, SourceRef

MAX_METADATA = 1024**2


def listing(body: bytes) -> ET.Element:
    if (
        len(body) > MAX_METADATA
        or b"<!DOCTYPE" in body.upper()
        or b"<!ENTITY" in body.upper()
    ):
        raise ValueError("Invalid source listing")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise ValueError("Invalid source listing") from error
    if root.tag.rsplit("}", 1)[-1] != "ListBucketResult":
        raise ValueError("Not a source object listing")
    return root


def listing_values(root: ET.Element, tag: str) -> tuple[str, ...]:
    return tuple(
        item.text or "" for item in root.iter() if item.tag.rsplit("}", 1)[-1] == tag
    )


def discover_runs(body: bytes) -> tuple[int, ...]:
    runs = []
    for prefix in listing_values(listing(body), "Prefix"):
        match = re.fullmatch(r"gfs\.(\d{8})/(00|06|12|18)/", prefix)
        if not match:
            if re.fullmatch(r"gfs\.\d{8}/", prefix) or not prefix:
                continue
            raise ValueError("Unsupported cycle prefix")
        try:
            run = datetime.strptime("".join(match.groups()), "%Y%m%d%H").replace(
                tzinfo=timezone.utc
            )
        except ValueError as error:
            raise ValueError("Invalid cycle date") from error
        runs.append(int(run.timestamp() * 1000))
    return tuple(sorted(set(runs), reverse=True))


def select_time(run_at_ms: int, leads: tuple[int, ...], target_ms: int) -> int | None:
    if not run_at_ms <= target_ms <= run_at_ms + 172800000:
        return None
    admitted = [lead for lead in leads if lead % 3600 == 0 and lead // 3600 in HORIZONS]
    return min(
        admitted,
        key=lambda lead: (abs(run_at_ms + lead * 1000 - target_ms), lead),
        default=None,
    )


def select_ranges(
    index: bytes,
    source: SourceRef,
    run_at_ms: int,
    lead_seconds: int,
    pressures_pa: tuple[int, ...],
) -> tuple[RangeRef, ...]:
    if (
        not index
        or len(index) > MAX_METADATA
        or not pressures_pa
        or len(pressures_pa) > 2
    ):
        raise ValueError("Unsupported inventory or pressure selection")
    if lead_seconds % 3600 or lead_seconds // 3600 not in HORIZONS:
        raise ValueError("Unsupported source lead")
    stamp = datetime.fromtimestamp(run_at_ms / 1000, timezone.utc).strftime(
        "d=%Y%m%d%H"
    )
    instant = "anl" if lead_seconds == 0 else f"{lead_seconds // 3600} hour fcst"
    records = []
    try:
        for line in index.decode("ascii").splitlines():
            fields = line.split(":")
            if len(fields) < 7 or int(fields[0]) != len(records) + 1:
                raise ValueError("Malformed inventory")
            records.append((int(fields[1]), fields[2:]))
    except (UnicodeError, IndexError) as error:
        raise ValueError("Malformed inventory") from error
    if (
        not records
        or records[0][0] != 0
        or any(
            not 0 <= start < source.size or (i and records[i - 1][0] >= start)
            for i, (start, _) in enumerate(records)
        )
    ):
        raise ValueError("Invalid source offsets")
    required = {
        (quantity, pressure): None
        for pressure in pressures_pa
        for quantity in ("u", "v", "t")
    }
    required[("sp", None)] = None
    result = []
    for i, (start, fields) in enumerate(records):
        quantity = {"TMP": "t", "UGRD": "u", "VGRD": "v", "PRES": "sp"}.get(fields[1])
        pressure = None
        if fields[2] != "surface":
            match = re.fullmatch(r"(\d+) mb", fields[2])
            pressure = int(match[1]) * 100 if match else -1
        key = quantity, pressure
        if key not in required:
            continue
        if required[key] is not None or fields[0] != stamp or fields[3] != instant:
            raise ValueError("Duplicate or inconsistent field identity")
        end = (records[i + 1][0] if i + 1 < len(records) else source.size) - 1
        if end - start + 1 > 32 * 1024**2:
            raise ValueError("Source field exceeds budget")
        ref = RangeRef(source, start, end, quantity, pressure)
        required[key] = ref
        result.append(ref)
    if any(value is None for value in required.values()):
        raise ValueError("Incomplete selected source fields")
    return tuple(result)


def available_pressures(index: bytes) -> tuple[int, ...]:
    """Find complete triplets; select_ranges separately verifies all identity."""
    if not index or len(index) > MAX_METADATA:
        raise ValueError("Invalid scientific pressure inventory")
    fields_by_pressure = {}
    try:
        for line in index.decode("ascii").splitlines():
            fields = line.split(":")
            if len(fields) < 7:
                raise ValueError("Malformed inventory")
            pressure = re.fullmatch(r"(\d+) mb", fields[4])
            if pressure and fields[3] in {"UGRD", "VGRD", "TMP"}:
                value = int(pressure[1]) * 100
                if 0 < value <= 110000:
                    fields_by_pressure.setdefault(value, set()).add(fields[3])
    except UnicodeError as error:
        raise ValueError("Malformed scientific pressure inventory") from error
    return tuple(
        sorted(
            p
            for p, names in fields_by_pressure.items()
            if names == {"UGRD", "VGRD", "TMP"}
        )
    )
