"""
Backward compatibility wrapper for route_eta_calculator module.

This file maintains backward compatibility by re-exporting all components
from the new app.services.route_eta module structure.

DEPRECATED: Import from app.services.route_eta instead.
"""

# Re-export everything from the new route_eta module
from app.services.route_eta import *  # noqa: F401, F403

__all__ = [  # noqa: F405
    "RouteETACalculator",
    "project_point_to_line_segment",
    "get_eta_cache_stats",
    "get_eta_accuracy_stats",
    "clear_eta_cache",
    "cleanup_eta_cache",
]
