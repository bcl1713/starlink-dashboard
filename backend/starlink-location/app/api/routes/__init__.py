"""Routes API module - KML route management endpoints."""

from fastapi import APIRouter

# Import routers from submodules
from app.api.routes import (
    management,
    upload,
    download,
    delete,
    stats,
    eta,
    timing,
    cache,
)

# Create main router with /api/routes prefix
router = APIRouter(prefix="/api/routes", tags=["routes"])

# Include all sub-routers
# Sub-routers have no prefix, so their paths are used as-is relative to /api/routes
router.include_router(management.router)
router.include_router(upload.router)
router.include_router(download.router)
router.include_router(delete.router)
router.include_router(stats.router)
router.include_router(eta.router)
router.include_router(timing.router)
router.include_router(cache.router)

__all__ = ["router"]
