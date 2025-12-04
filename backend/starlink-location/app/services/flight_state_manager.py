"""Compatibility shim for legacy flight_state_manager imports.

The implementation now lives in app.services.flight_state.manager. This shim
can be removed once all call sites are updated.
"""

from app.services.flight_state.manager import (  # noqa: F401
    FlightStateManager,
    get_flight_state_manager,
)

__all__ = ["FlightStateManager", "get_flight_state_manager"]
