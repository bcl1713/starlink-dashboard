"""Normalize actual stored-sample exports, never range-query lookback values."""

import hashlib
import json
import math

from .model import event, validate

NETWORK_FIELDS = (
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
)


CONTROL_FIELDS = NETWORK_FIELDS + (
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_altitude_feet",
    "starlink_dish_speed_knots",
    "starlink_dish_heading_degrees",
    "starlink_signal_quality_percent",
)


def stored_events(export, *, fields=CONTROL_FIELDS, run_id, segment="measured"):
    """Input must be Prometheus instant-query range-vector export, NOT query_range.

    Query each selected job/instance with {__name__=~"..."}[duration]; export
    stored values for up + metric families + scrape diagnostics in one matrix.
    The CLI requires an explicit stored-sample provenance attestation. The JSON
    matrix shape alone cannot distinguish stored samples from evaluated grids.
    """
    if export.get("status") != "success" or export["data"]["resultType"] != "matrix":
        raise ValueError("successful matrix export required")
    by_name = {}
    source_ids = set()
    for series in export["data"]["result"]:
        name = series["metric"]["__name__"]
        source_ids.add(
            hashlib.sha256(
                json.dumps(
                    {k: v for k, v in series["metric"].items() if k != "__name__"},
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )
        if name in by_name:
            raise ValueError("select a single job/instance/label set per family")
        values = {}
        for timestamp, value in series["values"]:
            timestamp, value = float(timestamp), float(value)
            if timestamp in values or not math.isfinite(timestamp) or math.isinf(value):
                raise ValueError("duplicate timestamp or infinity")
            values[timestamp] = value
        by_name[name] = values
    if len(source_ids) != 1:
        raise ValueError("matrix must use one coherent source label set")
    source_id = next(iter(source_ids))
    if not by_name.get("up"):
        raise ValueError("up stored samples required; cannot infer scrape success")
    rows = []
    for timestamp, up in sorted(by_name["up"].items()):
        for field in fields:
            value = by_name.get(field, {}).get(timestamp)
            state = (
                "failed"
                if up != 1
                else (
                    "missing"
                    if value is None
                    else "nan" if math.isnan(value) else "finite"
                )
            )
            data = {
                "series": field,
                "source_id": source_id,
                "timestamp": timestamp,
                "value": value if state == "finite" else None,
                "state": state,
                "segment": segment,
                "up": up if math.isfinite(up) else None,
            }
            for output, metric in [
                ("scrape_duration_seconds", "scrape_duration_seconds"),
                ("sample_count", "scrape_samples_scraped"),
            ]:
                v = by_name.get(metric, {}).get(timestamp)
                data[output] = v if v is not None and math.isfinite(v) else None
            rows.append(
                validate(
                    event(
                        "scrape",
                        data,
                        run_id=run_id,
                        stream_id="stored-export",
                        seq=len(rows) + 1,
                    )
                )
            )
    return rows
