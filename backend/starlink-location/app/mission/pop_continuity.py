"""Extract call capability without changing transport decisions or X optimizer costs."""

from app.mission.models import MissionLegTimeline
from app.mission.pop_coverage_evidence import manual_ka_unavailable
from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan


def _state(value):
    return {
        "available": "available",
        "degraded": "unavailable",
        "offline": "unavailable",
    }.get(value, "unknown")


def _policy_interval(segment):
    interval = segment.metadata.get("planning_interval")
    required = {
        "physical_x_state",
        "physical_ka_state",
        "physical_ku_state",
        "policy_x_state",
        "policy_ku_state",
        "raw_constraints",
        "physical_reasons",
        "start_time",
        "end_time",
    }
    if not isinstance(interval, dict) or not required <= interval.keys():
        return None
    from datetime import datetime

    try:
        if (
            datetime.fromisoformat(interval["start_time"]) > segment.start_time
            or datetime.fromisoformat(interval["end_time"]) < segment.end_time
        ):
            return None
    except (ValueError, TypeError):
        return None
    if not isinstance(interval["raw_constraints"], list):
        return None
    return interval


def _x_capability(segment):
    metadata = segment.metadata
    constraints = metadata.get("transport_constraints", {}).get("X")
    if metadata.get("planning_policy"):
        interval = _policy_interval(segment)
        if interval is None:
            return "unknown", False
        physical = _state(interval["physical_x_state"])
        operating = _state(interval["policy_x_state"])
        raw = set(interval["raw_constraints"]) | set(constraints or ())
        if physical == "unavailable" or raw - {"x_aft_cone"}:
            return "unavailable", False
        if physical == "unknown" or operating == "unknown":
            return "unknown", False
        concurrency = operating == "unavailable" and raw == {"x_aft_cone"}
        return operating, concurrency
    reasons = tuple(metadata.get("source_reasons", segment.reasons))
    hard_reason = any(
        any(
            token in reason.lower().replace("-", " ")
            for token in (
                "x aar",
                "x band / aar",
                "manual ar track",
                "x elevation",
                "x line of sight",
                "satellite swap",
                "x transition",
            )
        )
        for reason in reasons
    )
    if hard_reason:
        return "unavailable", False
    if constraints is not None:
        if any(c not in ("x_aft_cone", "x_azimuth") for c in constraints):
            return "unavailable", False
        if "x_azimuth" in constraints:
            return "unknown", False
        if constraints == ["x_aft_cone"]:
            import re

            known_reasons = all(
                re.fullmatch(
                    r"(?:X-Ku|Ku-X) Conflict(?: az=[\d.−-]+° el=[\d.−-]+°)?",
                    reason,
                    re.IGNORECASE,
                )
                or reason.lower().startswith(("ka ", "ku ", "safety-of-flight"))
                for reason in reasons
            )
            return ("unavailable", True) if known_reasons else ("unknown", False)
    if any(
        "conflict" in r.lower() and ("ku" in r.lower() or "starshield" in r.lower())
        for r in reasons
    ):
        return "unknown", False
    return _state(segment.x_state), False


def capabilities_from_timeline(
    timeline: MissionLegTimeline,
) -> tuple[CapabilitySpan, ...]:
    """Keep all independent constraints; absent prerequisites remain unknown."""
    result = []
    for segment in timeline.segments:
        interval = (
            _policy_interval(segment)
            if segment.metadata.get("planning_policy")
            else None
        )
        x, fallback = _x_capability(segment)
        if segment.metadata.get("planning_policy"):
            interval = interval if isinstance(interval, dict) else {}
            ka = _state(interval.get("physical_ka_state"))
            starshield = _state(interval.get("physical_ku_state"))
            if interval.get("policy_ku_state") == "offline":
                starshield = "unavailable"
        else:
            ka, starshield = _state(segment.ka_state), _state(segment.ku_state)
        evidence = timeline.statistics.get("_call_capability_evidence", {})
        if evidence.get("ka") is False:
            ka = (
                "unavailable" if manual_ka_unavailable(segment, evidence) else "unknown"
            )
        if (x == "available" or fallback) and evidence.get("x") is False:
            x, fallback = "unknown", False
        if evidence.get("starshield_enabled") is False:
            starshield = "unavailable"
        result.append(
            CapabilitySpan(
                start_utc=segment.start_time,
                end_utc=segment.end_time,
                ka=ka,
                x=x,
                starshield=starshield,
                x_concurrency_only=fallback,
                existing_call_outage=(ka == x == starshield == "unavailable"),
                source_ids=tuple(
                    dict.fromkeys(
                        (
                            segment.id,
                            *segment.metadata.get("source_segment_ids", ()),
                            *segment.metadata.get("source_reasons", segment.reasons),
                        )
                    )
                ),
            )
        )
    return tuple(result)


def attach_call_continuity(timeline: MissionLegTimeline) -> None:
    """Publish typed projection and separate overall totals after forecast capture."""
    timeline.call_continuity = None
    totals = (
        "planned_communications_outage_seconds",
        "pop_call_outage_seconds",
        "longest_call_outage_seconds",
    )
    for name in totals:
        timeline.statistics.pop(name, None)
    if timeline.pop_forecast is None or not timeline.segments:
        return
    timeline.call_continuity = project_call_continuity(
        timeline.pop_forecast,
        capabilities_from_timeline(timeline),
        start_utc=min(s.start_time for s in timeline.segments),
        end_utc=max(s.end_time for s in timeline.segments),
    )
    projection = timeline.call_continuity
    for name in totals:
        timeline.statistics[name] = getattr(projection, name)
