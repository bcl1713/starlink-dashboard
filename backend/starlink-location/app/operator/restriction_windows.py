"""Shared merged restriction windows for event projection and live timing."""

from .time_models import utc_timestamp


def _time(value):
    return utc_timestamp(value) if value is not None else None


def restriction_windows(model):
    """Yield the exact transport/cause windows emitted by the event feed."""
    if "_restriction_windows" in model:
        for window in model["_restriction_windows"]:
            if transport_event_allowed(model, window[0], window[3]):
                yield window
        return
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
        if end <= start or not transport_event_allowed(model, transport, start):
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


def compact_event_model(model):
    """Keep boundary events, not the thousands of samples that produced them."""
    result = {
        key: model[key]
        for key in (
            "transport_generations",
            "transport_availability",
            "transport_as_of",
            "_leg_id",
            "_event_source_ref",
            "route_geometry_identity",
            "pop_forecast",
            "pop_advisories",
            "call_continuity",
            "restriction_route",
            "restriction_boundaries",
            "unavailable_inputs",
            "time_basis",
            "boundary_times",
        )
        if key in model
    }
    result["_restriction_windows"] = tuple(restriction_windows(model))
    return result


def transport_event_allowed(model, transport, at):
    if transport is None or model.get("transport_availability") is None:
        return True
    from app.mission.availability_models import LegAvailability
    from app.mission.models import Transport

    snapshot = LegAvailability.model_validate(model["transport_availability"])
    key = Transport.KU if transport == "Starshield" else Transport(transport)
    from datetime import datetime

    raw = model.get("transport_as_of")
    now = (
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if isinstance(raw, str)
        else raw
    )
    return (now is None or snapshot.resolve(now)[key]) and (
        at is None or snapshot.resolve(at)[key]
    )


def transport_event_generation(model, transport):
    """Only that transport's changed eligibility renews future occurrences."""
    if transport is None or model.get("transport_availability") is None:
        return None
    from .event_ledger import identity

    key = "Ku" if transport == "Starshield" else transport
    raw = model["transport_availability"]
    failures = [f for f in raw.get("failures", []) if f["transport"] == key]
    configured = model.get("transport_generations", {}).get(key)
    if not failures and configured is None:
        return None
    return identity(key, failures, configured)
