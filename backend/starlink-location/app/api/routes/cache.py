"""Route cache management endpoints."""

from fastapi import APIRouter

from app.core.logging import get_logger
from app.services.route_eta_calculator import (
    get_eta_cache_stats,
    get_eta_accuracy_stats,
    clear_eta_cache,
    cleanup_eta_cache,
)

logger = get_logger(__name__)

router = APIRouter()


@router.get("/metrics/eta-cache", summary="Get ETA cache statistics")
async def get_eta_cache_metrics() -> dict:
    """Get statistics about ETA calculation caching performance.

    Retrieves current metrics about the ETA calculation cache including
    the number of entries, time-to-live settings, and last update timestamp.

    Returns:
        Dictionary containing cache_size, ttl_seconds, and last_updated timestamp

    Raises:
        No exceptions raised by this endpoint
    """
    return get_eta_cache_stats()


@router.get("/metrics/eta-accuracy", summary="Get ETA accuracy statistics")
async def get_eta_accuracy_metrics() -> dict:
    """Get ETA accuracy statistics from historical tracking.

    Retrieves accuracy metrics based on historical ETA predictions compared
    to actual arrival times, including error statistics and completion rates.

    Returns:
        Dictionary containing average_error, max_error, and completion_percentage

    Raises:
        No exceptions raised by this endpoint
    """
    return get_eta_accuracy_stats()


@router.post("/cache/cleanup", summary="Clean up expired cache entries")
async def cleanup_eta_cache_endpoint() -> dict:
    """Remove expired entries from the ETA cache.

    Scans the ETA calculation cache and removes all entries that have
    exceeded their time-to-live, freeing up memory.

    Returns:
        Dictionary with status="success", entries_removed count, and message

    Raises:
        No exceptions raised by this endpoint
    """
    removed = cleanup_eta_cache()
    return {
        "status": "success",
        "entries_removed": removed,
        "message": f"Cleaned up {removed} expired cache entries",
    }


@router.post("/cache/clear", summary="Clear all ETA cache")
async def clear_eta_cache_endpoint() -> dict:
    """Clear all cached ETA calculations (use with caution).

    Removes all entries from the ETA calculation cache, forcing recalculation
    for all subsequent requests. Use this endpoint sparingly as it impacts
    performance until the cache rebuilds.

    Returns:
        Dictionary with status="success" and descriptive message

    Raises:
        No exceptions raised by this endpoint
    """
    clear_eta_cache()
    return {"status": "success", "message": "ETA cache cleared"}
