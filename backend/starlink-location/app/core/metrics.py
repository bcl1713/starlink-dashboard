"""
Backward compatibility wrapper for metrics module.

This file maintains backward compatibility by re-exporting all metrics
from the new app.core.metrics module structure.

DEPRECATED: Import from app.core.metrics instead.
"""

# Re-export everything from the new metrics module
from app.core.metrics import *  # noqa: F401, F403
