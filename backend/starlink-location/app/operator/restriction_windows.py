"""Shared merged restriction windows for event projection and live timing."""

from .time_models import utc_timestamp


def _time(value):
    return utc_timestamp(value) if value is not None else None


def restriction_windows(model):
    """Yield the exact transport/cause windows emitted by the event feed."""
    spans = []
    for interval in (model.get("call_continuity") or {}).get("intervals", []):
        classification = interval["classification"]
        if classification in ("ordinary", "advisory", "x_fallback"):
            continue
        spans.append(
            (
                None,
                (
                    "call_outage"
                    if classification in ("planned_outage", "existing_outage")
                    else "advisory"
                ),
                tuple(sorted(interval.get("source_ids", []))),
                _time(interval["start_utc"]),
                _time(interval["end_utc"]),
            )
        )
    for capability in model.get("capability_spans", []):
        for transport, field in (
            ("Ka", "ka"),
            ("X", "x"),
            ("Starshield", "starshield"),
        ):
            if capability.get(field) != "unavailable":
                continue
            concurrent = field == "x" and capability.get("x_concurrency_only") is True
            spans.append(
                (
                    transport,
                    "degraded" if concurrent else "unavailable",
                    (
                        ("x_concurrency_only",)
                        if concurrent
                        else ("modeled_capability", transport)
                    ),
                    _time(capability["start_utc"]),
                    _time(capability["end_utc"]),
                )
            )
    for segment in (() if "capability_spans" in model else model.get("segments", [])):
        for transport, field in (
            ("Ka", "ka_state"),
            ("X", "x_state"),
            ("Starshield", "ku_state"),
        ):
            state = segment.get(field)
            if state in ("offline", "degraded"):
                spans.append(
                    (
                        transport,
                        "unavailable" if state == "offline" else "degraded",
                        tuple(sorted(segment.get("reasons") or [])),
                        _time(segment["start_time"]),
                        _time(segment["end_time"]),
                    )
                )
    # Combine adjacent same-cause restrictions before assigning ordered occurrence.
    groups = {}
    for transport, severity, causes, start, end in spans:
        if end <= start:
            continue
        groups.setdefault((transport, causes), []).append((start, end, severity))
    for (transport, causes), windows in groups.items():
        merged = []
        for start, end, severity in sorted(windows):
            if merged and start <= merged[-1][1] and merged[-1][2] == severity:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end), severity)
            else:
                merged.append((start, end, severity))
        for index, (start, end, severity) in enumerate(merged):
            yield transport, causes, index, start, end, severity
