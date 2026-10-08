"""Pure customer wording/grouping over the immutable availability projection."""

import json
from dataclasses import dataclass
from datetime import datetime

from .customer_clocks import CustomerRange, format_customer_range
from .snapshot import LegSnapshot
from .trial_clocks import EASTERN
from .trial_projection import TRANSPORT_NAMES, TrialInterval, TrialLeg

INCOMPLETE_X = (
    "X-Band planning incomplete — confirmed transport capability shown below."
)


@dataclass(frozen=True)
class CustomerRow:
    id: str
    start_time: datetime
    end_time: datetime
    clock: CustomerRange
    impact: str
    remaining: str
    posture: str
    interval_ids: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class CustomerLegView:
    leg_id: str
    title: str
    subtitle: str | None
    date_label: str
    timing_label: str
    notice: str | None
    intervals: tuple[TrialInterval, ...]
    rows: tuple[CustomerRow, ...]
    legend_required: bool


def confirmed_capability(interval: TrialInterval) -> str:
    names = [
        n
        for n, d in zip(("Ka", "Starshield", "X-Band"), interval.decisions)
        if d.value == "Up"
    ]
    return (
        " + ".join(names) + " confirmed"
        if names
        else "No transport confirmed available"
    )


def restriction_labels(interval: TrialInterval) -> tuple[str, ...]:
    labels = []
    for r in interval.restrictions:
        if r.kind == "sof":
            labels.append(
                "Landing SOF" if "landing" in r.label.lower() else "Takeoff SOF"
            )
        else:
            # AR labels are resolved coordination names, never raw reason strings.
            labels.append(r.label if r.label.startswith("AR-") else "Air refueling")
    return tuple(dict.fromkeys(labels))


def _key(interval):
    return (
        tuple((d.value, bool(d.limitation)) for d in interval.decisions),
        restriction_labels(interval),
        tuple((r.kind, r.start_time, r.end_time) for r in interval.restrictions),
        _impact(interval),
    )


def _impact(interval):
    parts = list(restriction_labels(interval))
    down = [n for n, d in zip(TRANSPORT_NAMES, interval.decisions) if d.value == "Down"]
    if len(down) == 3:
        parts.append("All transports unavailable")
    elif down:
        parts.append(" + ".join(down) + " unavailable")
    elif interval.limitations and not any(d.value == "?" for d in interval.decisions):
        parts.append("Transport coordination limitation")
    return "; ".join(parts) or "Assessment changed"


def project_customer_leg(
    captured: LegSnapshot, trial: TrialLeg, *, leg_number: int, leg_count: int
) -> CustomerLegView:
    if captured.leg_id != trial.leg_id or not 1 <= leg_number <= leg_count:
        raise ValueError("Customer leg identity/number mismatch")
    raw = json.loads(captured.leg_json)
    route = json.loads(captured.effective_route_json or b"{}")
    points = route.get("points") or []
    pair = []
    for key, index in (("departure_airport", 0), ("arrival_airport", -1)):
        point = points[index] if points else {}
        pair.append(raw.get(key) or point.get("name") or point.get("label"))
    identity = (
        " → ".join(map(str, pair))
        if all(pair)
        else raw.get("name") or f"Leg {leg_number}"
    )
    subtitle = None
    if (
        all(pair)
        and points
        and points[0].get("location_name")
        and points[-1].get("location_name")
    ):
        subtitle = points[0]["location_name"] + " → " + points[-1]["location_name"]
    title = f"LEG {leg_number} OF {leg_count} — {identity}"
    notice = None
    if trial.intervals and all(i.decisions[2].value == "?" for i in trial.intervals):
        notice = INCOMPLETE_X
    elif any(d.value == "?" for i in trial.intervals for d in i.decisions):
        notice = "Transport assessment incomplete — confirmed capability shown below."
    if not trial.utc_bounds:
        return CustomerLegView(
            trial.leg_id,
            title,
            subtitle,
            "",
            "Flight timing unavailable",
            "Flight timing/data incomplete — confirmed information only.",
            trial.intervals,
            (),
            leg_number == 1,
        )
    departure, arrival = trial.utc_bounds
    flight = format_customer_range(departure, arrival, departure)
    minutes = int((arrival - departure).total_seconds() // 60)
    timing = (
        f"DEP {flight.start} | ARR {flight.end} | {minutes // 60}h {minutes % 60:02d}m"
    )
    varying_assessment = {
        n for n in range(3) if len({i.decisions[n].value for i in trial.intervals}) > 1
    }
    groups = []
    previous = None
    for interval in trial.intervals:
        selected = (
            bool(interval.restrictions)
            or any(interval.decisions[n].value == "?" for n in varying_assessment)
            or any(d.value == "Down" for d in interval.decisions)
            or (
                bool(interval.limitations)
                and not any(d.value == "?" for d in interval.decisions)
            )
        )
        if selected:
            if (
                groups
                and previous is not None
                and previous.end_time == interval.start_time
                and _key(previous) == _key(interval)
            ):
                groups[-1].append(interval)
            else:
                groups.append([interval])
        previous = interval if selected else None
    rows = []
    for n, intervals in enumerate(groups, 1):
        first, last = intervals[0], intervals[-1]
        uncertain = any(d.value == "?" for d in first.decisions)
        remaining = (
            confirmed_capability(first)
            if uncertain
            else (" + ".join(first.remaining_transports) or "None")
        )
        rows.append(
            CustomerRow(
                f"{trial.leg_id}-customer-{n:03d}",
                first.start_time,
                last.end_time,
                format_customer_range(first.start_time, last.end_time, departure),
                _impact(first),
                remaining,
                "Assessment incomplete" if uncertain else first.posture,
                tuple(i.id for i in intervals),
                tuple(dict.fromkeys(s for i in intervals for s in i.active_source_ids)),
            )
        )
    return CustomerLegView(
        trial.leg_id,
        title,
        subtitle,
        departure.astimezone(EASTERN).strftime("%d %b %Y"),
        timing,
        notice,
        trial.intervals,
        tuple(rows),
        leg_number == 1,
    )
