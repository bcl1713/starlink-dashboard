"""Flight state management service with automatic phase detection."""

# For now, re-export from the original file to maintain structure
# Future refactoring can split this further if needed
from app.services.flight_state_manager import (
    FlightStateManager,
    get_flight_state_manager,
)

__all__ = ["FlightStateManager", "get_flight_state_manager"]
