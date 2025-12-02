"""POI API module - CRUD, ETA calculations, and statistics endpoints."""

from fastapi import APIRouter

from . import crud, etas, stats

# Create the main POI router by combining all sub-routers
# Set prefix here so all sub-routers share the same /api/pois prefix
# IMPORTANT: Include more specific routes (etas, stats) BEFORE less specific ones (crud)
# to prevent the /{poi_id} route from catching /etas and /count/total paths
router = APIRouter(prefix="/api/pois")
router.include_router(etas.router)
router.include_router(stats.router)
router.include_router(crud.router)


def set_coordinator(coordinator):
    """Set the simulation coordinator reference for all POI modules."""
    crud.set_coordinator(coordinator)
    etas.set_coordinator(coordinator)
    stats.set_coordinator(coordinator)


__all__ = ["router", "set_coordinator"]
