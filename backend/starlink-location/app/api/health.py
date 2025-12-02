"""Health check endpoint handler."""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

# Global health state
_coordinator: Optional[object] = None
_last_metrics_scrape_time = None

# Health check thresholds
PROMETHEUS_SCRAPE_TIMEOUT_SECONDS = (
    30  # If scrape hasn't happened in 30s, degrade health
)


def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator


def get_last_scrape_time():
    """Get the last metrics scrape time from the metrics module."""
    try:
        from app.api.metrics import get_last_scrape_time as get_scrape_time

        return get_scrape_time()
    except Exception:
        return None


def _get_metrics_count():
    """Count the number of metrics in the registry."""
    try:
        from app.core.metrics import REGISTRY

        return len(list(REGISTRY.collect()))
    except Exception:
        return 0


def _get_active_route():
    """Return active parsed route if available."""
    if _coordinator is None:
        return None

    route_manager = getattr(_coordinator, "route_manager", None)
    if route_manager:
        try:
            return route_manager.get_active_route()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Unable to fetch active route from coordinator: %s", exc)

    return None


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return datetime with UTC tzinfo; assumes naive timestamps are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _compute_time_until_departure(
    now: datetime, status_snapshot, timing_profile
) -> Optional[float]:
    """Compute seconds until departure using flight status and timing profile."""
    departure_time = None
    if status_snapshot:
        departure_time = _ensure_utc(getattr(status_snapshot, "departure_time", None))

    if departure_time:
        delta = departure_time - now
        return max(0.0, delta.total_seconds())

    if timing_profile:
        scheduled_departure = _ensure_utc(timing_profile.departure_time)
        if scheduled_departure:
            delta = scheduled_departure - now
            return delta.total_seconds()

    return None


def _safe_isoformat(dt: Optional[datetime]) -> Optional[str]:
    """Return ISO-8601 string for datetime, normalizing to UTC."""
    dt = _ensure_utc(dt)
    if dt is None:
        return None
    return dt.isoformat()


@router.get("/health")
async def health():
    """
    Health check endpoint with Prometheus monitoring status.

    Returns JSON with service status, uptime, operating mode, and Prometheus scrape information,
    plus current flight-state metadata when available.
    """
    if _coordinator is None:
        raise HTTPException(status_code=503, detail="Service not yet initialized")

    try:
        uptime = _coordinator.get_uptime_seconds()

        # Get Prometheus scrape status
        last_scrape = get_last_scrape_time()
        metrics_count = _get_metrics_count()

        # Determine if Prometheus is actively scraping
        is_scraping = False
        scrape_iso_time = None
        detail = None

        if last_scrape is not None:
            time_since_scrape = time.time() - last_scrape
            is_scraping = time_since_scrape < PROMETHEUS_SCRAPE_TIMEOUT_SECONDS

            # Format last scrape time as ISO 8601
            scrape_iso_time = datetime.fromtimestamp(
                last_scrape, tz=timezone.utc
            ).isoformat()

            if not is_scraping:
                detail = f"Prometheus has not scraped metrics in the last {PROMETHEUS_SCRAPE_TIMEOUT_SECONDS} seconds"
        else:
            # No scrape has happened yet
            detail = "Prometheus has not scraped metrics yet"

        # Get actual operating mode from coordinator property
        actual_mode = getattr(_coordinator, "mode", "unknown")

        # Determine message based on mode and connection status
        if actual_mode == "live":
            dish_connected = bool(_coordinator.is_connected())
            message = (
                "Live mode: connected to dish"
                if dish_connected
                else "Live mode: waiting for dish connection"
            )
        else:
            dish_connected = None
            message = "Simulation mode: generating test data"

        response = {
            "status": "ok" if is_scraping else "degraded",
            "uptime_seconds": uptime,
            "mode": actual_mode,
            "message": message,
            "version": "0.2.0",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "prometheus_last_scrape": scrape_iso_time,
            "metrics_count": metrics_count,
        }

        if dish_connected is not None:
            response["dish_connected"] = dish_connected

        # Attach flight status metadata
        status_snapshot = None
        try:
            from app.services.flight_state_manager import get_flight_state_manager

            flight_state_manager = get_flight_state_manager()
            status_snapshot = flight_state_manager.get_status()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Flight state unavailable for health response: %s", exc)

        now = datetime.now(tz=timezone.utc)
        active_route = _get_active_route()
        timing_profile = active_route.timing_profile if active_route else None

        if status_snapshot:
            response["flight_phase"] = status_snapshot.phase.value
            response["eta_mode"] = status_snapshot.eta_mode.value
            if status_snapshot.active_route_id:
                response["active_route_id"] = status_snapshot.active_route_id
            if status_snapshot.active_route_name:
                response["active_route_name"] = status_snapshot.active_route_name
            response["has_route_timing_data"] = status_snapshot.has_timing_data
            if status_snapshot.scheduled_departure_time:
                response["scheduled_departure_time"] = _safe_isoformat(
                    status_snapshot.scheduled_departure_time
                )
            if status_snapshot.scheduled_arrival_time:
                response["scheduled_arrival_time"] = _safe_isoformat(
                    status_snapshot.scheduled_arrival_time
                )
            if status_snapshot.departure_time:
                response["actual_departure_time"] = _safe_isoformat(
                    status_snapshot.departure_time
                )
            if status_snapshot.arrival_time:
                response["actual_arrival_time"] = _safe_isoformat(
                    status_snapshot.arrival_time
                )
            if status_snapshot.time_until_departure_seconds is not None:
                response["time_until_departure_seconds"] = (
                    status_snapshot.time_until_departure_seconds
                )
            if status_snapshot.time_since_departure_seconds is not None:
                response["time_since_departure_seconds"] = (
                    status_snapshot.time_since_departure_seconds
                )

        if timing_profile:
            if timing_profile.departure_time:
                response.setdefault(
                    "scheduled_departure_time",
                    _safe_isoformat(timing_profile.departure_time),
                )
            if timing_profile.arrival_time:
                response.setdefault(
                    "scheduled_arrival_time",
                    _safe_isoformat(timing_profile.arrival_time),
                )
            if timing_profile.actual_departure_time:
                response.setdefault(
                    "actual_departure_time",
                    _safe_isoformat(timing_profile.actual_departure_time),
                )
            if timing_profile.actual_arrival_time:
                response.setdefault(
                    "actual_arrival_time",
                    _safe_isoformat(timing_profile.actual_arrival_time),
                )
            response["flight_status"] = timing_profile.flight_status

        if active_route:
            try:
                active_route_id = Path(active_route.metadata.file_path).stem
            except Exception:
                active_route_id = active_route.metadata.file_path
            response.setdefault("active_route_id", active_route_id)
            response.setdefault("active_route_name", active_route.metadata.name)
            if "has_route_timing_data" not in response and timing_profile:
                response["has_route_timing_data"] = bool(timing_profile.has_timing_data)

        if "time_until_departure_seconds" not in response:
            time_until_departure = _compute_time_until_departure(
                now, status_snapshot, timing_profile
            )
            if time_until_departure is not None:
                response["time_until_departure_seconds"] = time_until_departure

        if detail:
            response["detail"] = detail

        # Allow degraded responses to return 200 for startup compatibility
        if not is_scraping:
            return response

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
