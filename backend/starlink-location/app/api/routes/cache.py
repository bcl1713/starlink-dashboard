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
    """
    Get statistics about ETA calculation caching performance.

    Returns:
    - Dictionary with cache size, TTL, and timestamp
    """
    return get_eta_cache_stats()


@router.get("/metrics/eta-accuracy", summary="Get ETA accuracy statistics")
async def get_eta_accuracy_metrics() -> dict:
    """
    Get ETA accuracy statistics from historical tracking.

    Returns:
    - Dictionary with average error, max error, completion percentage
    """
    return get_eta_accuracy_stats()


@router.post("/cache/cleanup", summary="Clean up expired cache entries")
async def cleanup_eta_cache_endpoint() -> dict:
    """
    Remove expired entries from the ETA cache.

    Returns:
    - Dictionary with number of entries removed
    """
    removed = cleanup_eta_cache()
    return {
        "status": "success",
        "entries_removed": removed,
        "message": f"Cleaned up {removed} expired cache entries",
    }


@router.post("/cache/clear", summary="Clear all ETA cache")
async def clear_eta_cache_endpoint() -> dict:
    """
    Clear all cached ETA calculations (use with caution).

    Returns:
    - Dictionary with status
    """
    clear_eta_cache()
    return {"status": "success", "message": "ETA cache cleared"}
