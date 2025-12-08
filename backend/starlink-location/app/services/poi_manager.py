"""Legacy compatibility shim for POI management.

The real implementation now lives in app.services.poi.manager. This module
re-exports the class so existing imports keep working during the transition.
"""

from app.models.poi import POI, POICreate, POIUpdate
from app.services.poi.manager import POIManager, logger

__all__ = ["POIManager", "POICreate", "POIUpdate", "POI", "logger"]
