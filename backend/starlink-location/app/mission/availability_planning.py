"""Pure eligibility helpers shared by captured planning and legacy timelines."""

import itertools

from app.mission.availability_models import LegAvailability, Transport


def leg_snapshot(leg):
    """Resolve standalone leg defaults without consulting any mission store."""
    from app.mission.availability import resolved_leg_availability
    from app.mission.models import Mission

    return resolved_leg_availability(
        Mission(id="standalone", name="Standalone", legs=[leg]), leg
    )


def eligible(snapshot, transport, at):
    return snapshot is None or snapshot.resolve(at).get(transport, True)


def usable_during(snapshot, transport, start, end):
    return any(
        eligible(snapshot, transport, t)
        for t in (start, *(snapshot.boundaries(start, end) if snapshot else ()))
    )


def apply_timeline_availability(timeline, snapshot: LegAvailability):
    """Split at half-open failure edges and retain all independent constraints."""
    from app.mission.models import TimelineStatus, TransportState

    segments = []
    for source in timeline.segments:
        edges = (
            source.start_time,
            *snapshot.boundaries(source.start_time, source.end_time),
            source.end_time,
        )
        for start, end in itertools.pairwise(edges):
            state = snapshot.resolve(start)
            segment = source.model_copy(
                deep=True, update={"start_time": start, "end_time": end}
            )
            for transport, field in (
                (Transport.X, "x_state"),
                (Transport.KA, "ka_state"),
                (Transport.KU, "ku_state"),
            ):
                if not state[transport]:
                    setattr(segment, field, TransportState.OFFLINE)
                    reason = f'{"Starshield" if transport == Transport.KU else transport.value} unavailable'
                    segment.reasons.append(reason)
                    segment.metadata.setdefault(
                        "source_reasons", list(source.reasons)
                    ).append(reason)
            segment.metadata["transport_availability"] = {
                t.value: v for t, v in state.items()
            }
            segment.impacted_transports = [
                t
                for t, field in (
                    (Transport.X, "x_state"),
                    (Transport.KA, "ka_state"),
                    (Transport.KU, "ku_state"),
                )
                if getattr(segment, field) != TransportState.AVAILABLE
            ]
            if any(not v for v in state.values()):
                segment.status = (
                    TimelineStatus.CRITICAL
                    if len(segment.impacted_transports) > 1
                    else TimelineStatus.DEGRADED
                )
            segments.append(segment)
    timeline.segments = segments
    timeline.statistics["_transport_availability"] = snapshot.model_dump(mode="json")
