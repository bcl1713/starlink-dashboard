"""Mission v2 API endpoints for hierarchical mission management."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.mission.models import Mission, MissionLeg
from app.mission.storage import (
    save_mission_v2,
    load_mission_v2,
    delete_mission,
    mission_exists,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/missions", tags=["missions-v2"])
