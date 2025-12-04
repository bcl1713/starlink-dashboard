"""ETA cache and history tracking for route calculations."""

# Global cache instance (singleton pattern)
from app.services.eta_cache import ETACache, ETAHistoryTracker

_eta_cache = ETACache(ttl_seconds=5.0)
_eta_history = ETAHistoryTracker(max_history=100)


def get_eta_cache_stats() -> dict:
    """
    Get statistics about the global ETA cache.

    Returns:
        Dictionary with cache metrics
    """
    return _eta_cache.stats()


def get_eta_accuracy_stats() -> dict:
    """
    Get ETA accuracy statistics from historical tracking.

    Returns:
        Dictionary with accuracy metrics
    """
    return _eta_history.get_accuracy_stats()


def clear_eta_cache() -> None:
    """Clear all cached ETA calculations."""
    _eta_cache.clear()


def cleanup_eta_cache() -> int:
    """
    Clean up expired entries in the ETA cache.

    Returns:
        Number of expired entries removed
    """
    return _eta_cache.cleanup_expired()
