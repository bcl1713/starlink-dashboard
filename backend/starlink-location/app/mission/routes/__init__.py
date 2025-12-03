"""Mission routes API module - split into focused sub-modules.

This module organizes mission API endpoints into logical groups:
- missions.py: CRUD operations (create, read, update, delete)
- activation.py: Mission activation and deactivation
- operations.py: Timeline management and export functionality
- utils.py: Shared utility functions and models
"""

from fastapi import APIRouter

from .missions import (
    router as missions_router,
    create_mission,
    update_mission,
)
from .activation import router as activation_router, get_active_mission_id
from .operations import router as operations_router

# Create combined router for all mission operations
router = APIRouter()

# Include all sub-routers
router.include_router(missions_router)
router.include_router(activation_router)
router.include_router(operations_router)

# Export public API
__all__ = [
    "router",
    "get_active_mission_id",
    "create_mission",
    "update_mission",
]
