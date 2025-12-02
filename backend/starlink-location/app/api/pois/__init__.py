"""POI API module - CRUD, ETA calculations, and statistics endpoints."""

from fastapi import APIRouter

from . import crud, etas, stats

# Create the main POI router by combining all sub-routers
router = APIRouter()
router.include_router(crud.router)
router.include_router(etas.router)
router.include_router(stats.router)


def set_coordinator(coordinator):
    """Set the simulation coordinator reference for all POI modules."""
    crud.set_coordinator(coordinator)
    etas.set_coordinator(coordinator)
    stats.set_coordinator(coordinator)


__all__ = ["router", "set_coordinator"]
