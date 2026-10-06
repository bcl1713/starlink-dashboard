"""Bounded, source-shaped AWC feeds normalized to provider-neutral GeoJSON.

Flight category uses the worst of visibility and AGL ceiling: LIFR is below
1 statute mile or 500 feet, IFR below 3 miles or 1,000 feet, MVFR at or below
5 miles or 3,000 feet, otherwise VFR. Unknown fields span all categories;
lower-bound visibility spans every category permitted by that bound. Publish a
category only when every possible combination gives the same worst category.
Thus explicit CLR/SKC/FEW/SCT without ceiling permits VFR, a missing sky report
does not, and a known LIFR field remains LIFR even if the other field is unknown.
Never interpret an empty or capped source feed as worldwide clear weather.
"""

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from shapely.affinity import translate
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon, box, mapping

from .relations import cancellation_matches

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_NORMALIZED_BYTES = 16 * 1024 * 1024
MAX_STATIONS = 5000
MAX_ADVISORIES = 500
MAX_VERTICES = 100000
_KNOT_MPS = 1852 / 3600
_MILE_M = 1609.344
_FOOT_M = 0.3048
_INHG_PA = 3386.389
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_CATEGORY_NAMES = ["VFR", "MVFR", "IFR", "LIFR"]


class _BudgetError(ValueError):
    """Resource bounds reject the generation, rather than hiding locations."""


def _input(raw: bytes, now_ms: int) -> None:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("invalid or oversized AWC source")
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("invalid retrieval instant")


def _collection(
    features: list, now_ms: int, omitted: int = 0, partial: bool = False
) -> dict:
    result = {
        "type": "FeatureCollection",
        "features": features,
        "feed_completeness": "partial" if partial or omitted else "unknown",
        "omitted_features": omitted,
        "source_id": "awc",
        "retrieved_at_ms": now_ms,
    }
    if len(_canonical(result)) > MAX_NORMALIZED_BYTES:
        raise ValueError("normalized AWC source exceeds byte budget")
    return result


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _instant(value) -> int:
    if not isinstance(value, str):
        raise ValueError(  # noqa: TRY004 - Invalid source uses the ValueError contract.
            "AWC instant must be an explicit UTC-offset timestamp"
        )
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("AWC instant must include a UTC offset")
        delta = instant.astimezone(timezone.utc) - _EPOCH
        result = (
            delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000
        )
        if result < 0:
            raise ValueError("negative AWC instant")
        return result
    except (TypeError, OverflowError) as error:
        raise ValueError("invalid AWC instant") from error


def _interval(start, end) -> tuple[int, int]:
    first, last = _instant(start), _instant(end)
    if first >= last:
        raise ValueError("invalid AWC validity interval")
    return first, last


def _text(node: ET.Element, name: str) -> str | None:
    value = node.findtext(name)
    return value.strip() if value and value.strip() else None


def _string(value, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError("invalid AWC text field")
    return value.strip() or None


def _number(value, *, minimum=None, maximum=None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(  # noqa: TRY004 - Invalid source uses the ValueError contract.
            "invalid AWC number"
        )
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("invalid AWC number") from error
    if (
        not math.isfinite(number)
        or (minimum is not None and number < minimum)
        or (maximum is not None and number > maximum)
    ):
        raise ValueError("invalid AWC number")
    return number


def _scaled(value, factor: float, *, minimum=None, offset: float = 0) -> float | None:
    number = _number(value, minimum=minimum)
    return None if number is None else number * factor + offset


def _xml(raw: bytes, now_ms: int, product: str) -> list[ET.Element]:
    _input(raw, now_ms)
    # Only UTF-8 XML is accepted. Null bytes rule out UTF-16/32 declarations that
    # could otherwise conceal DTD/entities from the declaration check.
    if b"\x00" in raw or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", raw, re.IGNORECASE):
        raise ValueError("unsafe AWC XML declaration")
    try:
        root = ET.fromstring(raw.decode("utf-8-sig"))
    except (ET.ParseError, UnicodeError, ValueError) as error:
        raise ValueError("malformed AWC XML") from error
    if root.tag != "response" or len(root.findall("data")) != 1:
        raise ValueError("invalid AWC XML response")
    errors = root.find("errors")
    if errors is not None and (len(errors) or (errors.text and errors.text.strip())):
        raise ValueError("AWC source returned an error")
    source = root.find("data_source")
    if (
        source is not None
        and source.get("name")
        not in {"METAR": {"metar", "metars"}, "TAF": {"taf", "tafs"}}[product]
    ):
        raise ValueError("incorrect AWC XML product")
    data = root.find("data")
    records = list(data)
    if any(record.tag != product for record in records):
        raise ValueError("incorrect AWC XML record")
    count = data.get("num_results")
    if count is not None:
        try:
            if int(count) != len(records) or not count.isdigit():
                raise ValueError("inconsistent AWC record count")
        except ValueError as error:
            raise ValueError("inconsistent AWC record count") from error
    return records


def _position(node: ET.Element) -> list[float]:
    lon = _number(_text(node, "longitude"), minimum=-180, maximum=180)
    lat = _number(_text(node, "latitude"), minimum=-90, maximum=90)
    if lon is None or lat is None:
        raise ValueError("missing AWC station coordinates")
    return [lon, lat]


def _visibility(node: ET.Element, raw: str = "") -> tuple[float | None, bool]:
    value = _text(node, "visibility_statute_mi")
    if value is None:
        return None, False
    lower = value.endswith("+") or value.startswith((">", "P"))
    cleaned = value.rstrip("+").lstrip(">P").strip()
    number = _number(cleaned, minimum=0)
    # AWC sometimes decodes P6SM/9999 to a plain numeric XML field. Only the
    # observation's own raw text is consulted, never the entire multi-group TAF.
    lower = lower or bool(re.search(r"\bP\d+(?:\.\d+)?SM\b|(?<!\d)9999(?!\d)", raw))
    return number * _MILE_M, lower


def _ceiling(node: ET.Element) -> tuple[float | None, bool, float | None]:
    layers = node.findall("sky_condition")
    heights = []
    unknown = False
    known_report = bool(layers)
    for layer in layers:
        cover = layer.get("sky_cover")
        if cover in {"BKN", "OVC", "OVX", "VV"}:
            height = _number(layer.get("cloud_base_ft_agl"), minimum=0)
            if height is None and cover in {"OVX", "VV"}:
                height = _number(_text(node, "vert_vis_ft"), minimum=0)
            if height is None:
                unknown = True
            else:
                heights.append(height * _FOOT_M)
        elif cover not in {"CLR", "SKC", "NSC", "NCD", "CAVOK", "FEW", "SCT"}:
            unknown = True
    vertical = _number(_text(node, "vert_vis_ft"), minimum=0)
    if vertical is not None:
        heights.append(vertical * _FOOT_M)
        known_report = True
    # An unknown broken layer may be lower than any known ceiling.
    bound = min(heights) if heights else None
    return (None if unknown else bound), known_report and not unknown, bound


def _visibility_rank(value: float) -> int:
    if value < _MILE_M:
        return 3
    if value < 3 * _MILE_M:
        return 2
    if value <= 5 * _MILE_M:
        return 1
    return 0


def _category(
    visibility, lower: bool, ceiling, ceiling_known: bool, ceiling_upper_bound=None
) -> str | None:
    if visibility is None:
        vis = set(range(4))
    elif lower:
        vis = set(range(_visibility_rank(visibility) + 1))
    else:
        vis = {_visibility_rank(visibility)}
    if not ceiling_known:
        # A known cloud base is an upper bound on the lowest ceiling even when
        # another ceiling layer is missing its height.
        bound_rank = (
            (
                3
                if ceiling_upper_bound < 500 * _FOOT_M
                else (
                    2
                    if ceiling_upper_bound < 1000 * _FOOT_M
                    else 1 if ceiling_upper_bound <= 3000 * _FOOT_M else 0
                )
            )
            if ceiling_upper_bound is not None
            else 0
        )
        sky = set(range(bound_rank, 4))
    elif ceiling is None:
        sky = {0}
    else:
        sky = {
            (
                3
                if ceiling < 500 * _FOOT_M
                else (
                    2
                    if ceiling < 1000 * _FOOT_M
                    else 1 if ceiling <= 3000 * _FOOT_M else 0
                )
            )
        }
    possible = {max(v, c) for v in vis for c in sky}
    return _CATEGORY_NAMES[possible.pop()] if len(possible) == 1 else None


def _weather(node: ET.Element, raw: str = "") -> tuple[dict, tuple[bool, float | None]]:
    direction = _text(node, "wind_dir_degrees")
    variable = direction == "VRB" or bool(
        re.search(r"\bVRB\d{2,3}(?:G\d{2,3})?(?:KT|MPS|KMH)\b", raw)
    )
    visibility, lower = _visibility(node, raw)
    ceiling, ceiling_known, ceiling_upper_bound = _ceiling(node)
    result = {
        "wind_direction_deg": (
            None if variable else _number(direction, minimum=0, maximum=360)
        ),
        "wind_variable": variable,
        "wind_speed_mps": _scaled(_text(node, "wind_speed_kt"), _KNOT_MPS, minimum=0),
        "gust_mps": _scaled(_text(node, "wind_gust_kt"), _KNOT_MPS, minimum=0),
        "visibility_m": visibility,
        "visibility_lower_bound": lower,
        "ceiling_m": ceiling,
        "ceiling_known": ceiling_known,
        "weather_codes": (_text(node, "wx_string") or "").split(),
    }
    return result, (ceiling_known, ceiling_upper_bound)


def _station(node: ET.Element, report_type: str, weather: dict) -> dict:
    station = _text(node, "station_id")
    if (
        station is None
        or len(station) > 64
        or not re.fullmatch(r"[A-Za-z0-9_-]+", station)
    ):
        raise ValueError("invalid AWC station identity")
    raw = _text(node, "raw_text")
    if raw is None:
        raise ValueError("missing AWC raw bulletin")
    p = {
        "station_id": station,
        "report_type": report_type,
        "raw_text": raw,
        "observed_at_ms": None,
        "issued_at_ms": None,
        "valid_from_ms": None,
        "valid_to_ms": None,
        **weather,
        "ceiling_reference": "AGL",
        "pressure_pa": None,
        "temperature_k": None,
        "dewpoint_k": None,
        "flight_category": None,
        "forecast_groups": [],
    }
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": _position(node)},
        "properties": p,
    }


def _stations(features: list, now_ms: int, time_key: str, invalid: int = 0) -> dict:
    latest = {}
    for feature in features:
        p = feature["properties"]
        feature["id"] = (
            f'{p["station_id"]}:{p["report_type"]}:{p[time_key]}:'
            + hashlib.sha256(_canonical(feature)).hexdigest()[:16]
        )
        station = p["station_id"]
        previous = latest.get(station)
        # Source order cannot choose between tied revisions.
        if previous is None or (p[time_key], feature["id"]) > (
            previous["properties"][time_key],
            previous["id"],
        ):
            latest[station] = feature
    ordered = [latest[station] for station in sorted(latest)]
    omitted = invalid + max(0, len(ordered) - MAX_STATIONS)
    return _collection(ordered[:MAX_STATIONS], now_ms, omitted)


def _metar(node: ET.Element, now_ms: int) -> dict | None:
    observed = _instant(_text(node, "observation_time"))
    report_type = _text(node, "metar_type") or (
        "SPECI" if (_text(node, "raw_text") or "").startswith("SPECI ") else "METAR"
    )
    if report_type not in {"METAR", "SPECI"}:
        raise ValueError("invalid AWC observation report type")
    weather, (known, ceiling_upper_bound) = _weather(
        node, _text(node, "raw_text") or ""
    )
    feature = _station(node, report_type, weather)
    p = feature["properties"]
    p.update(
        observed_at_ms=observed,
        fresh_until_ms=observed + 75 * 60000,
        expires_at_ms=observed + 120 * 60000,
        pressure_pa=_scaled(_text(node, "altim_in_hg"), _INHG_PA, minimum=0),
        temperature_k=_scaled(_text(node, "temp_c"), 1, minimum=-273.15, offset=273.15),
        dewpoint_k=_scaled(
            _text(node, "dewpoint_c"), 1, minimum=-273.15, offset=273.15
        ),
        flight_category=_category(
            weather["visibility_m"],
            weather["visibility_lower_bound"],
            weather["ceiling_m"],
            known,
            ceiling_upper_bound,
        ),
    )
    return (
        feature if p["expires_at_ms"] > now_ms and observed <= now_ms + 60000 else None
    )


def normalize_metar(raw_xml: bytes, now_ms: int) -> dict:
    """Normalize current METAR/SPECI; malformed records disclose partial coverage."""
    features, invalid = [], 0
    for node in _xml(raw_xml, now_ms, "METAR"):
        try:
            feature = _metar(node, now_ms)
        except ValueError:
            invalid += 1
        else:
            if feature is not None:
                features.append(feature)
    return _stations(features, now_ms, "observed_at_ms", invalid)


def _taf(node: ET.Element, now_ms: int) -> dict | None:
    issued = _instant(_text(node, "issue_time"))
    start, end = _interval(_text(node, "valid_time_from"), _text(node, "valid_time_to"))
    forecasts = node.findall("forecast")
    if not forecasts:
        raise ValueError("AWC TAF has no forecast groups")
    groups, base_weather, base_known, base_ceiling_bound, effective_key = (
        [],
        None,
        False,
        None,
        None,
    )
    for index, group in enumerate(forecasts):
        first, last = _interval(
            _text(group, "fcst_time_from"), _text(group, "fcst_time_to")
        )
        if first < start or last > end:
            raise ValueError("AWC forecast group outside TAF validity")
        weather, (known, ceiling_upper_bound) = _weather(group)
        probability = _number(_text(group, "probability"), minimum=0, maximum=100)
        if probability is not None and not probability.is_integer():
            raise ValueError("invalid AWC probability")
        change = _text(group, "change_indicator")
        completion = _text(group, "time_becoming")
        becoming = _instant(completion) if completion is not None else None
        if becoming is not None and not first <= becoming <= last:
            raise ValueError("AWC BECMG completion outside forecast validity")
        groups.append(
            {
                "change_type": change,
                "probability": None if probability is None else int(probability),
                "valid_from_ms": first,
                "valid_to_ms": last,
                "time_becoming_ms": becoming,
                **weather,
            }
        )
        effective = becoming if change == "BECMG" else first
        prevailing = change in {None, "FM", "BECMG"} and probability is None
        key = (effective, change is not None, index) if effective is not None else None
        if (
            prevailing
            and effective is not None
            and start <= now_ms < end
            and first <= now_ms < last
            and effective <= now_ms
            and (effective_key is None or key > effective_key)
        ):
            base_weather, base_known, base_ceiling_bound, effective_key = (
                weather,
                known,
                ceiling_upper_bound,
                key,
            )
    if base_weather is None:
        base_weather, (base_known, base_ceiling_bound) = _weather(
            ET.Element("forecast")
        )
    feature = _station(node, "TAF", base_weather)
    feature["properties"].update(
        issued_at_ms=issued,
        valid_from_ms=start,
        valid_to_ms=end,
        expires_at_ms=end,
        fresh_until_ms=min(end, now_ms + 20 * 60000),
        forecast_groups=groups,
        flight_category=_category(
            base_weather["visibility_m"],
            base_weather["visibility_lower_bound"],
            base_weather["ceiling_m"],
            base_known,
            base_ceiling_bound,
        ),
    )
    return feature if end > now_ms else None


def normalize_taf(raw_xml: bytes, now_ms: int) -> dict:
    """Keep source groups; malformed records disclose partial coverage."""
    features, invalid = [], 0
    for node in _xml(raw_xml, now_ms, "TAF"):
        try:
            feature = _taf(node, now_ms)
        except ValueError:
            invalid += 1
        else:
            if feature is not None:
                features.append(feature)
    return _stations(features, now_ms, "issued_at_ms", invalid)


def _vertical(raw: str) -> dict:
    unknown = {"lower": None, "upper": None, "reference": "unknown", "unit": "unknown"}
    flights = list(
        re.finditer(r"\b(SFC|FL\d{2,3})\s*/\s*((?:FL)?\d{2,3})\b", raw, re.IGNORECASE)
    )
    heights = list(
        re.finditer(r"\b(\d+)\s*/\s*(\d+)\s*(FT|M)\s+(MSL|AGL)\b", raw, re.IGNORECASE)
    )
    tops = list(re.finditer(r"\bTOP\s+FL(\d{2,3})\b", raw, re.IGNORECASE))
    if re.search(r"\bTOP\s+(?:ABV|BLW)\b", raw, re.IGNORECASE):
        return unknown
    if len(flights) + len(heights) + len(tops) != 1:
        return unknown
    if flights:
        match = flights[0]
        # Terrain surface has no known standard-pressure FL coordinate.
        lower = None if match[1].upper() == "SFC" else int(match[1][2:])
        if match[1].upper() == "SFC" and not match[2].upper().startswith("FL"):
            return unknown
        upper = int(match[2].upper().removeprefix("FL"))
        result = {
            "lower": lower,
            "upper": upper,
            "reference": "FL",
            "unit": "flight-level",
        }
    elif tops:
        result = {
            "lower": None,
            "upper": int(tops[0][1]),
            "reference": "FL",
            "unit": "flight-level",
        }
    else:
        match = heights[0]
        factor = _FOOT_M if match[3].upper() == "FT" else 1
        result = {
            "lower": int(match[1]) * factor,
            "upper": int(match[2]) * factor,
            "reference": match[4].upper(),
            "unit": "m",
        }
    return (
        result
        if result["lower"] is None or result["lower"] <= result["upper"]
        else unknown
    )


def _polygons(geometry) -> list:
    if not isinstance(geometry, dict):
        raise ValueError(  # noqa: TRY004 - Invalid source uses the ValueError contract.
            "unlocated advisory"
        )
    if geometry.get("type") == "Polygon":
        polygons = [geometry.get("coordinates")]
    elif geometry.get("type") == "MultiPolygon":
        polygons = geometry.get("coordinates")
    else:
        raise ValueError("unsupported advisory geometry")
    if (
        not isinstance(polygons, list)
        or not polygons
        or any(
            not isinstance(p, list) or not p or any(not isinstance(r, list) for r in p)
            for p in polygons
        )
    ):
        raise ValueError("invalid advisory coordinates")
    return polygons


def _vertex_count(geometry) -> int:
    try:
        return sum(len(ring) for polygon in _polygons(geometry) for ring in polygon)
    except ValueError:
        return 0


def _unwrap_ring(ring: list) -> list:
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("advisory ring must be closed")
    output = []
    for position in ring:
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            raise ValueError("invalid advisory position")
        lon, lat = position
        if (
            type(lon) not in (int, float)
            or type(lat) not in (int, float)
            or not math.isfinite(lon)
            or not math.isfinite(lat)
            or not -360 <= lon <= 360
            or not -90 <= lat <= 90
        ):
            raise ValueError("invalid advisory position")
        if output:
            while lon - output[-1][0] > 180:
                lon -= 360
            while lon - output[-1][0] < -180:
                lon += 360
        output.append((lon, lat))
    if (
        output[0] != output[-1]
        or max(p[0] for p in output) - min(p[0] for p in output) >= 360
    ):
        raise ValueError("ambiguous globe winding")
    return output


def _split_geometry(geometry, budget: int) -> tuple[dict, int]:
    polygons = _polygons(geometry)
    if sum(len(r) for p in polygons for r in p) > budget:
        raise _BudgetError("advisory source vertex budget exceeded")
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
            raise ValueError("invalid advisory polygon")
        source.append(polygon)
        first = math.floor((polygon.bounds[0] + 180) / 360)
        last = math.floor((polygon.bounds[2] + 180) / 360)
        for strip in range(first, last + 1):
            clipped = polygon.intersection(
                box(-180 + strip * 360, -90, 180 + strip * 360, 90)
            )
            parts = (
                [clipped]
                if clipped.geom_type == "Polygon"
                else (
                    list(clipped.geoms)
                    if clipped.geom_type in {"MultiPolygon", "GeometryCollection"}
                    else []
                )
            )
            for part in parts:
                if part.geom_type == "Polygon" and not part.is_empty and part.area > 0:
                    pieces.append(translate(part, xoff=-360 * strip))
    if not MultiPolygon(source).is_valid or not pieces:
        raise ValueError("invalid advisory multipolygon")
    output = pieces[0] if len(pieces) == 1 else MultiPolygon(pieces)
    if not output.is_valid or not math.isclose(
        sum(p.area for p in source), output.area, rel_tol=1e-10, abs_tol=1e-9
    ):
        raise ValueError("advisory split changed topology")
    count = sum(
        len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors) for p in pieces
    )
    if count > budget:
        raise _BudgetError("advisory split vertex budget exceeded")
    # Shapely mapping uses tuples; the public contract is strict JSON lists.
    return json.loads(json.dumps(mapping(output))), count


def _day_time(token: str, anchor_ms: int) -> int | None:
    """Resolve bulletin DDHHMM to the closest month around authoritative UTC."""
    anchor = _EPOCH + timedelta(milliseconds=anchor_ms)
    day, hour, minute = int(token[:2]), int(token[2:4]), int(token[4:])
    if hour > 24 or minute > 59 or (hour == 24 and minute != 0):
        return None
    candidates = []
    for shift in (-1, 0, 1):
        month_index = anchor.year * 12 + anchor.month - 1 + shift
        year, month = divmod(month_index, 12)
        try:
            candidate = datetime(year, month + 1, day, tzinfo=timezone.utc) + timedelta(
                hours=hour, minutes=minute
            )
        except ValueError:
            continue
        candidates.append(_instant(candidate.isoformat()))
    return (
        min(candidates, key=lambda value: abs(value - anchor_ms))
        if candidates
        else None
    )


def _bulletin_series(raw: str, provider_series: str | None) -> str | None:
    # The raw declared identity also joins AWC's observed/forecast geometry
    # variants. Never remove an arbitrary F from a provider identity.
    match = re.search(
        r"\bSIGMET\s+([A-Z0-9]+(?:[ \t]+[A-Z0-9]+)*?)\s+VALID\s+\d{6}\s*/\s*\d{6}\b",
        raw,
        re.IGNORECASE,
    )
    if match:
        return " ".join(match[1].upper().split())
    return provider_series


def _cancellation_target(raw: str, anchor_ms: int) -> dict | None:
    matches = list(
        re.finditer(
            r"\b(?:CNL|CANCELLED|CANCELED)\s+SIGMET\s+"
            r"([A-Z0-9]+(?:[ \t]+[A-Z0-9]+)*?)"
            r"(?:[ \t]+(?:VALID[ \t]+)?(\d{6})[ \t]*/[ \t]*(\d{6})"
            r"|(?=[ \t]*(?:[.\n=]|$)))",
            raw,
            re.IGNORECASE,
        )
    )
    if len(matches) != 1:
        return None
    match = matches[0]
    series = " ".join(match[1].upper().split())
    if len(series) > 64:
        return None
    first = _day_time(match[2], anchor_ms) if match[2] else None
    last = (
        _day_time(match[3], first if first is not None else anchor_ms)
        if match[3]
        else None
    )
    if (match[2] or match[3]) and (first is None or last is None or first >= last):
        return None
    return {"series": series, "valid_from_ms": first, "valid_to_ms": last}


def normalize_sigmet(raw_geojson: bytes, now_ms: int) -> dict:
    """Preserve text, altitude evidence and cancellation identity, split locations."""
    _input(raw_geojson, now_ms)
    try:
        collection = json.loads(raw_geojson)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("malformed AWC advisory JSON") from error
    if (
        not isinstance(collection, dict)
        or collection.get("type") != "FeatureCollection"
        or not isinstance(collection.get("features"), list)
    ):
        raise ValueError("invalid AWC advisory response")
    records = collection["features"]
    if len(records) > MAX_ADVISORIES:
        raise ValueError("AWC advisory feature budget exceeded")
    if (
        sum(_vertex_count(f.get("geometry")) for f in records if isinstance(f, dict))
        > MAX_VERTICES
    ):
        raise ValueError("AWC advisory source vertex budget exceeded")
    features, used_vertices = [], 0
    for record in records:
        if (
            not isinstance(record, dict)
            or record.get("type") != "Feature"
            or not isinstance(record.get("properties"), dict)
        ):
            raise ValueError("invalid AWC advisory feature")
        p = record["properties"]
        raw = _string(p.get("rawSigmet"), required=True)
        first, last = _interval(p.get("validTimeFrom"), p.get("validTimeTo"))
        issuer, fir, series = (
            _string(p.get(key)) for key in ("icaoId", "firId", "seriesId")
        )
        cancelled = p.get("cancelled") is True or bool(
            re.search(r"\b(?:CNL|CANCELLED|CANCELED)\b", raw, re.IGNORECASE)
        )
        revision = _string(p.get("revision"))
        if revision is None:
            token = re.search(r"\b(AMD|COR)\b", raw, re.IGNORECASE)
            revision = token[1].upper() if token else None
        bulletin_series = _bulletin_series(raw, series)
        issued_match = re.search(
            r"^\s*[A-Z]{4}\d{2}\s+[A-Z]{4}\s+(\d{6})\b", raw, re.IGNORECASE
        )
        issued = _day_time(issued_match[1], first) if issued_match else None
        target = _cancellation_target(raw, first) if cancelled else None
        amends = _string(p.get("amends"))
        if amends is None and (target is not None or revision):
            relation_series = (
                target["series"] if target is not None else bulletin_series
            )
            amends = "/".join(
                (issuer or "unknown", fir or "unknown", relation_series or "unknown")
            )
        properties = {
            "issuer": issuer,
            "fir": fir,
            "series": series,
            "revision": revision,
            "phenomenon": _string(p.get("hazard")),
            "severity": _string(p.get("qualifier")),
            "raw_text": raw,
            "valid_from_ms": first,
            "valid_to_ms": last,
            "vertical": _vertical(raw),
            "cancelled": cancelled,
            "amends": amends,
            "bulletin_series": bulletin_series,
            "cancellation_target": target,
            "issued_at_ms": issued,
            "expires_at_ms": last,
        }
        geometry = None
        if not cancelled and last > now_ms:
            try:
                geometry, count = _split_geometry(
                    record.get("geometry"), MAX_VERTICES - used_vertices
                )
                used_vertices += count
            except _BudgetError:
                raise
            except (ValueError, TypeError, GEOSException):
                # A location failure never erases the bulletin's textual warning.
                pass
        feature = {"type": "Feature", "geometry": geometry, "properties": properties}
        feature["id"] = hashlib.sha256(_canonical(feature)).hexdigest()
        if last > now_ms:
            features.append(feature)
    # Cancellation geometry is never rendered; a currently valid cancellation
    # also suppresses a matching original polygon returned by the same feed.
    cancellations = [
        f["properties"]
        for f in features
        if f["properties"]["cancelled"]
        and f["properties"]["valid_from_ms"] <= now_ms < f["properties"]["valid_to_ms"]
    ]
    for feature in features:
        p = feature["properties"]
        if not p["cancelled"] and any(
            cancellation_matches(p, cancellation) for cancellation in cancellations
        ):
            feature["geometry"] = None
    partial = (
        collection.get("truncated") is True
        or collection.get("hasMore") is True
        or bool(collection.get("next"))
    )
    return _collection(sorted(features, key=lambda f: f["id"]), now_ms, partial=partial)
