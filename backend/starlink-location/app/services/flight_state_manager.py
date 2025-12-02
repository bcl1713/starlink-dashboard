"""Flight state management service with automatic phase detection and transition."""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

from app.models.flight_status import FlightPhase, ETAMode, FlightStatus

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from app.models.route import ParsedRoute

logger = logging.getLogger(__name__)


def _normalize_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return datetime normalized to UTC (assumes naive timestamps are already UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class FlightStateManager:
    """
    Manages flight state with automatic phase transitions.

    Features:
    - Automatic departure detection based on speed threshold
    - Automatic arrival detection based on distance and dwell time
    - Manual phase transitions with optional logging
    - Thread-safe singleton pattern
    - Speed persistence tracking to prevent false positives

    Configuration Constants:
    - DEPARTURE_SPEED_THRESHOLD_KNOTS: 50.0 (trigger speed for departure)
    - DEPARTURE_SPEED_PERSISTENCE_SECONDS: 10.0 (time above threshold to confirm)
    - ARRIVAL_DISTANCE_THRESHOLD_M: 100.0 (distance to final waypoint for arrival)
    - ARRIVAL_DWELL_TIME_SECONDS: 60.0 (time near final waypoint to confirm arrival)
    """

    # Configuration constants
    DEPARTURE_SPEED_THRESHOLD_KNOTS = 50.0
    DEPARTURE_SPEED_PERSISTENCE_SECONDS = 10.0
    ARRIVAL_DISTANCE_THRESHOLD_M = 100.0
    ARRIVAL_DWELL_TIME_SECONDS = 60.0

    _instance: Optional["FlightStateManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "FlightStateManager":
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize flight state manager (only once due to singleton)."""
        if self._initialized:
            return

        self._initialized = True
        self._lock = threading.Lock()

        # Current flight status
        self._status = FlightStatus(
            phase=FlightPhase.PRE_DEPARTURE,
            eta_mode=ETAMode.ANTICIPATED,
        )
        self._status.active_route_id = None
        self._status.active_route_name = None
        self._status.has_timing_data = False
        self._status.scheduled_departure_time = None
        self._status.scheduled_arrival_time = None
        self._status.time_until_departure_seconds = None
        self._status.time_since_departure_seconds = None

        # Speed persistence tracking
        self._speed_persistence_seconds = 0.0
        self._last_speed_sample_time: Optional[datetime] = None
        self._above_threshold_start_time: Optional[datetime] = None

        # Arrival tracking
        self._arrival_start_time: Optional[datetime] = None
        self._arrival_distance_at_start: Optional[float] = None

        # Callbacks for state changes
        self._phase_change_callbacks: list[
            Callable[[FlightPhase, FlightPhase], None]
        ] = []
        self._mode_change_callbacks: list[Callable[[ETAMode, ETAMode], None]] = []

        logger.info(
            f"FlightStateManager initialized: {self._status.phase.value} / {self._status.eta_mode.value}"
        )

    def get_status(self) -> FlightStatus:
        """
        Get current flight status.

        Returns:
            Current FlightStatus instance
        """
        with self._lock:
            status_copy = FlightStatus(
                phase=self._status.phase,
                eta_mode=self._status.eta_mode,
                active_route_id=self._status.active_route_id,
                active_route_name=self._status.active_route_name,
                has_timing_data=self._status.has_timing_data,
                scheduled_departure_time=self._status.scheduled_departure_time,
                scheduled_arrival_time=self._status.scheduled_arrival_time,
                departure_time=self._status.departure_time,
                arrival_time=self._status.arrival_time,
                speed_persistence_seconds=self._status.speed_persistence_seconds,
                last_departure_check_time=self._status.last_departure_check_time,
                last_arrival_check_time=self._status.last_arrival_check_time,
            )

        now_utc = datetime.now(timezone.utc)
        departure_utc = _normalize_to_utc(status_copy.departure_time)
        scheduled_departure_utc = _normalize_to_utc(
            status_copy.scheduled_departure_time
        )

        # Compute time since departure (only positive values)
        if departure_utc and now_utc >= departure_utc:
            status_copy.time_since_departure_seconds = (
                now_utc - departure_utc
            ).total_seconds()
        else:
            status_copy.time_since_departure_seconds = None

        # Compute countdown until departure (pre-departure only)
        if status_copy.phase == FlightPhase.PRE_DEPARTURE:
            if departure_utc and departure_utc > now_utc:
                status_copy.time_until_departure_seconds = (
                    departure_utc - now_utc
                ).total_seconds()
            elif scheduled_departure_utc:
                status_copy.time_until_departure_seconds = (
                    scheduled_departure_utc - now_utc
                ).total_seconds()
            else:
                status_copy.time_until_departure_seconds = None
        else:
            status_copy.time_until_departure_seconds = 0.0

        return status_copy

    def check_departure(self, current_speed_knots: float) -> bool:
        """
        Check for departure based on speed threshold with persistence.

        Departure is detected when:
        - Current speed exceeds DEPARTURE_SPEED_THRESHOLD_KNOTS
        - Speed remains above threshold for DEPARTURE_SPEED_PERSISTENCE_SECONDS
        - Currently in PRE_DEPARTURE phase

        Args:
            current_speed_knots: Current aircraft speed in knots

        Returns:
            True if departure was triggered, False otherwise
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self._status.last_departure_check_time = now

            # Only check if in pre-departure phase
            if self._status.phase != FlightPhase.PRE_DEPARTURE:
                return False

            # Track speed samples for persistence
            if self._last_speed_sample_time is None:
                self._last_speed_sample_time = now

            # Initialize persistence tracking if above threshold
            if current_speed_knots > self.DEPARTURE_SPEED_THRESHOLD_KNOTS:
                if self._above_threshold_start_time is None:
                    self._above_threshold_start_time = now
                    logger.debug(
                        f"Speed {current_speed_knots:.1f}kn exceeds departure threshold "
                        f"({self.DEPARTURE_SPEED_THRESHOLD_KNOTS}kn), starting persistence check"
                    )

                # Check if speed has been above threshold long enough
                if self._above_threshold_start_time is not None:
                    persistence_seconds = (
                        now - self._above_threshold_start_time
                    ).total_seconds()
                    self._status.speed_persistence_seconds = persistence_seconds

                    if persistence_seconds >= self.DEPARTURE_SPEED_PERSISTENCE_SECONDS:
                        # Trigger departure
                        if self._status.departure_time is None:
                            self._status.departure_time = now
                        self._transition_to_phase(FlightPhase.IN_FLIGHT)
                        logger.info(
                            f"Departure detected: speed {current_speed_knots:.1f}kn "
                            f"sustained for {persistence_seconds:.1f}s"
                        )
                        return True
            else:
                # Speed dropped below threshold, reset persistence tracking
                if self._above_threshold_start_time is not None:
                    logger.debug(
                        f"Speed {current_speed_knots:.1f}kn dropped below threshold, "
                        f"resetting persistence check"
                    )
                    self._above_threshold_start_time = None
                    self._status.speed_persistence_seconds = 0.0

            self._last_speed_sample_time = now
            return False

    def check_arrival(
        self,
        distance_to_destination_m: float,
        current_speed_knots: float,
    ) -> bool:
        """
        Check for arrival based on distance and dwell time.

        Arrival is detected when:
        - Aircraft is within ARRIVAL_DISTANCE_THRESHOLD_M of destination
        - Aircraft has remained in this zone for ARRIVAL_DWELL_TIME_SECONDS
        - Currently in IN_FLIGHT phase

        Args:
            distance_to_destination_m: Distance to final destination in meters
            current_speed_knots: Current aircraft speed in knots (for context)

        Returns:
            True if arrival was triggered, False otherwise
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self._status.last_arrival_check_time = now

            # Only check if in flight phase
            if self._status.phase != FlightPhase.IN_FLIGHT:
                return False

            # Check if within arrival distance
            if distance_to_destination_m <= self.ARRIVAL_DISTANCE_THRESHOLD_M:
                # Start or continue tracking arrival time
                if self._arrival_start_time is None:
                    self._arrival_start_time = now
                    self._arrival_distance_at_start = distance_to_destination_m
                    logger.debug(
                        f"Aircraft within arrival zone ({distance_to_destination_m:.0f}m), "
                        f"starting dwell time check"
                    )

                # Check if aircraft has been in arrival zone long enough
                if self._arrival_start_time is not None:
                    dwell_seconds = (now - self._arrival_start_time).total_seconds()

                    if dwell_seconds >= self.ARRIVAL_DWELL_TIME_SECONDS:
                        # Trigger arrival
                        if self._status.arrival_time is None:
                            self._status.arrival_time = now
                        self._transition_to_phase(FlightPhase.POST_ARRIVAL)
                        logger.info(
                            f"Arrival detected: {dwell_seconds:.1f}s in arrival zone "
                            f"({distance_to_destination_m:.0f}m from destination)"
                        )
                        return True
            else:
                # Aircraft left arrival zone, reset tracking
                if self._arrival_start_time is not None:
                    logger.debug(
                        "Aircraft left arrival zone, resetting dwell time check"
                    )
                    self._arrival_start_time = None
                    self._arrival_distance_at_start = None

            return False

    def transition_phase(
        self, new_phase: FlightPhase, reason: Optional[str] = None
    ) -> bool:
        """
        Manually transition to a new flight phase.

        Args:
            new_phase: Target flight phase
            reason: Optional reason for the transition (for logging)

        Returns:
            True if transition was successful, False if invalid
        """
        with self._lock:
            if new_phase == self._status.phase:
                logger.debug(
                    f"Already in {new_phase.value} phase, no transition needed"
                )
                return False

            old_phase = self._status.phase

            # Prepare timestamps based on target phase before transition
            if (
                new_phase == FlightPhase.IN_FLIGHT
                and self._status.departure_time is None
            ):
                self._status.departure_time = datetime.now(timezone.utc)
            elif (
                new_phase == FlightPhase.POST_ARRIVAL
                and self._status.arrival_time is None
            ):
                self._status.arrival_time = datetime.now(timezone.utc)
            elif new_phase == FlightPhase.PRE_DEPARTURE:
                # Manual reset clears arrival tracking
                self._status.departure_time = None
                self._status.arrival_time = None
                self._status.speed_persistence_seconds = 0.0
                self._above_threshold_start_time = None
                self._arrival_start_time = None
                self._arrival_distance_at_start = None

            # Perform transition
            self._transition_to_phase(new_phase)

            reason_str = f" ({reason})" if reason else ""
            logger.info(
                f"Manual phase transition: {old_phase.value} → {new_phase.value}{reason_str}"
            )

            return True

    def reset(self) -> None:
        """Reset flight state to initial PRE_DEPARTURE phase."""
        self.transition_phase(FlightPhase.PRE_DEPARTURE, reason="reset")

    def register_phase_change_callback(
        self, callback: Callable[[FlightPhase, FlightPhase], None]
    ) -> None:
        """
        Register a callback to be called when flight phase changes.

        Callback signature: callback(old_phase: FlightPhase, new_phase: FlightPhase)

        Args:
            callback: Function to call on phase change
        """
        self._phase_change_callbacks.append(callback)

    def register_mode_change_callback(
        self, callback: Callable[[ETAMode, ETAMode], None]
    ) -> None:
        """
        Register a callback to be called when ETA mode changes.

        Callback signature: callback(old_mode: ETAMode, new_mode: ETAMode)

        Args:
            callback: Function to call on mode change
        """
        self._mode_change_callbacks.append(callback)

    # ------------------------------------------------------------------ #
    # Route context management
    # ------------------------------------------------------------------ #

    def update_route_context(
        self,
        route: Optional["ParsedRoute"],
        *,
        auto_reset: bool = True,
        reason: Optional[str] = None,
    ) -> None:
        """
        Synchronize the active route context with the flight state manager.

        Args:
            route: ParsedRoute instance to associate, or None to clear context
            auto_reset: Whether to reset flight state when route changes
            reason: Optional log annotation for why the context changed
        """
        new_route_id: Optional[str] = None
        new_route_name: Optional[str] = None
        scheduled_departure = None
        scheduled_arrival = None
        has_timing_data = False

        if route is not None:
            try:
                file_path = route.metadata.file_path
                new_route_id = (
                    Path(file_path).stem if file_path else route.metadata.name
                )
            except Exception:  # pragma: no cover - defensive guard
                new_route_id = route.metadata.name
            new_route_name = route.metadata.name
            if route.timing_profile:
                has_timing_data = bool(route.timing_profile.has_timing_data)
                scheduled_departure = route.timing_profile.departure_time
                scheduled_arrival = route.timing_profile.arrival_time

        reset_needed = False
        previous_route_id: Optional[str]

        with self._lock:
            previous_route_id = self._status.active_route_id
            self._status.active_route_id = new_route_id
            self._status.active_route_name = new_route_name
            self._status.has_timing_data = has_timing_data
            self._status.scheduled_departure_time = scheduled_departure
            self._status.scheduled_arrival_time = scheduled_arrival

            if auto_reset and previous_route_id != new_route_id:
                reset_needed = True
                self._status.departure_time = None
                self._status.arrival_time = None
                self._status.speed_persistence_seconds = 0.0
                self._status.last_departure_check_time = None
                self._status.last_arrival_check_time = None
                self._above_threshold_start_time = None
                self._arrival_start_time = None
                self._arrival_distance_at_start = None

            if route and route.timing_profile:
                if reset_needed:
                    route.timing_profile.actual_departure_time = None
                    route.timing_profile.actual_arrival_time = None
                    route.timing_profile.flight_status = FlightPhase.PRE_DEPARTURE.value
                else:
                    route.timing_profile.flight_status = self._status.phase.value

        if reset_needed:
            reset_reason = reason or (
                "route_cleared" if route is None else f"route_changed:{new_route_id}"
            )
            logger.info(
                "Flight state reset due to route context change (route_id=%s, reason=%s)",
                new_route_id,
                reset_reason,
            )
            self.transition_phase(FlightPhase.PRE_DEPARTURE, reason=reset_reason)

    def clear_route_context(self, reason: Optional[str] = None) -> None:
        """Convenience wrapper for clearing the active route context."""
        self.update_route_context(
            None, auto_reset=True, reason=reason or "route_cleared"
        )

    # ------------------------------------------------------------------ #
    # Manual triggers
    # ------------------------------------------------------------------ #

    def trigger_departure(
        self, timestamp: Optional[datetime] = None, reason: Optional[str] = None
    ) -> bool:
        """
        Manually trigger departure and transition to IN_FLIGHT phase.

        Args:
            timestamp: Optional explicit departure timestamp (defaults to now)
            reason: Optional reason string for logging

        Returns:
            True if a transition occurred, False if already in-flight or beyond
        """
        with self._lock:
            if self._status.phase == FlightPhase.IN_FLIGHT:
                logger.debug("Departure trigger ignored: already in-flight")
                return False

            departure_time = _normalize_to_utc(timestamp) or datetime.now(timezone.utc)
            self._status.departure_time = departure_time
            self._status.last_departure_check_time = datetime.now(timezone.utc)
            self._status.speed_persistence_seconds = 0.0
            self._above_threshold_start_time = None

            old_phase = self._status.phase
            self._transition_to_phase(FlightPhase.IN_FLIGHT)

        logger.info(
            "Manual departure trigger invoked (previous_phase=%s, timestamp=%s, reason=%s)",
            old_phase.value,
            departure_time.isoformat(),
            reason,
        )
        return True

    def trigger_arrival(
        self, timestamp: Optional[datetime] = None, reason: Optional[str] = None
    ) -> bool:
        """
        Manually trigger arrival and transition to POST_ARRIVAL phase.

        Args:
            timestamp: Optional explicit arrival timestamp (defaults to now)
            reason: Optional reason string for logging

        Returns:
            True if a transition occurred, False if already post-arrival
        """
        with self._lock:
            if self._status.phase == FlightPhase.POST_ARRIVAL:
                logger.debug("Arrival trigger ignored: already post-arrival")
                return False

            arrival_time = _normalize_to_utc(timestamp) or datetime.now(timezone.utc)
            self._status.arrival_time = arrival_time
            self._status.last_arrival_check_time = datetime.now(timezone.utc)
            self._arrival_start_time = None
            self._arrival_distance_at_start = None

            old_phase = self._status.phase
            self._transition_to_phase(FlightPhase.POST_ARRIVAL)

        logger.info(
            "Manual arrival trigger invoked (previous_phase=%s, timestamp=%s, reason=%s)",
            old_phase.value,
            arrival_time.isoformat(),
            reason,
        )
        return True

    # Private methods

    def _transition_to_phase(self, new_phase: FlightPhase) -> None:
        """
        Internal phase transition with automatic mode updates.

        Rules:
        - PRE_DEPARTURE → ETA mode is ANTICIPATED
        - IN_FLIGHT → ETA mode is ESTIMATED
        - POST_ARRIVAL → ETA mode remains ESTIMATED

        Args:
            new_phase: Target flight phase
        """
        old_phase = self._status.phase
        self._status.phase = new_phase

        # Update ETA mode based on phase
        old_mode = self._status.eta_mode
        if new_phase == FlightPhase.PRE_DEPARTURE:
            self._status.eta_mode = ETAMode.ANTICIPATED
        elif new_phase == FlightPhase.IN_FLIGHT:
            self._status.eta_mode = ETAMode.ESTIMATED
        # POST_ARRIVAL keeps current mode (ESTIMATED)

        # Call registered callbacks
        if old_phase != new_phase:
            for callback in self._phase_change_callbacks:
                try:
                    callback(old_phase, new_phase)
                except Exception as e:
                    logger.error(f"Error in phase change callback: {e}")

        if old_mode != self._status.eta_mode:
            for callback in self._mode_change_callbacks:
                try:
                    callback(old_mode, self._status.eta_mode)
                except Exception as e:
                    logger.error(f"Error in mode change callback: {e}")


# Singleton instance access
def get_flight_state_manager() -> FlightStateManager:
    """Get the singleton FlightStateManager instance."""
    return FlightStateManager()
