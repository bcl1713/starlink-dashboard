"""One eligibility resolver for planning and operational mission consumers."""

from datetime import datetime

from .availability_models import FailureWindow, LegAvailability
from .models import Mission, MissionLeg, Transport


def resolved_leg_availability(mission: Mission, leg: MissionLeg) -> LegAvailability:
    """Freeze planned eligibility and the current run's operational windows.

    Explicit leg keys supersede mission keys; a missing Ku key in both places
    preserves the old leg's starshield_enabled setting. No coverage inference
    (including unknown PoP/location) participates in eligibility.
    """
    settings = mission.availability
    overrides = leg.transports.availability_overrides or {}
    planned = {}
    for transport in Transport:
        if transport in overrides:
            planned[transport] = overrides[transport]
        elif transport in settings.defaults:
            planned[transport] = settings.defaults[transport]
        elif transport == Transport.KU:
            planned[transport] = leg.transports.starshield_enabled is not False
        else:
            planned[transport] = True

    active = {}
    windows = []
    for record in settings.history:
        if record.simulation_run_id != settings.simulation_run_id:
            continue
        if record.unavailable:
            active.setdefault(record.transport, record.effective_at)
        elif record.transport in active:
            windows.append(
                FailureWindow(
                    transport=record.transport,
                    start=active.pop(record.transport),
                    end=record.effective_at,
                )
            )
    windows.extend(
        FailureWindow(transport=transport, start=start)
        for transport, start in active.items()
    )
    return LegAvailability(
        mission_id=mission.id,
        leg_id=leg.id,
        revision=settings.revision,
        simulation_run_id=settings.simulation_run_id,
        planned=tuple(planned.items()),
        failures=tuple(windows),
    )


def resolve_availability(
    mission: Mission, leg: MissionLeg, at: datetime
) -> dict[Transport, bool]:
    """Resolve planned eligibility with failure taking precedence at an instant."""
    return resolved_leg_availability(mission, leg).resolve(at)


def availability_boundaries(
    mission: Mission, leg: MissionLeg, start: datetime, end: datetime
) -> tuple[datetime, ...]:
    """Return operational change instants strictly inside the evaluation range."""
    return resolved_leg_availability(mission, leg).boundaries(start, end)
