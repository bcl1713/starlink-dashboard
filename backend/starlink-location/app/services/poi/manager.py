"""POI manager for loading, saving, and managing points of interest."""

# For now, re-export from the original file to maintain structure
# Future refactoring can split this further if needed
from app.services.poi_manager import POIManager

__all__ = ["POIManager"]
