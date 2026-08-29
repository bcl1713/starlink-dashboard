"""Mission routes API module - split into focused sub-modules.

This module organizes mission API endpoints into logical groups:
- missions.py: CRUD operations (create, read, update, delete)
- activation.py: Mission activation and deactivation
- operations.py: Timeline management and export functionality
- utils.py: Shared utility functions and models
"""

from fastapi import APIRouter

from .activation import get_active_mission_id
from .activation import router as activation_router
from .missions import (
    create_mission,
    update_mission,
)
from .missions import (
    router as missions_router,
)
from .operations import router as operations_router

# Create combined router for all mission operations
router = APIRouter()

# Include all sub-routers
# Note: activation_router must be included before missions_router so that
# /api/missions/active (specific) takes precedence over /api/missions/{id} (generic)
router.include_router(activation_router)
router.include_router(missions_router)
router.include_router(operations_router)

# Export public API
__all__ = [
    "create_mission",
    "get_active_mission_id",
    "router",
    "update_mission",
]
