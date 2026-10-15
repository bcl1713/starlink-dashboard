"""Strict contracts shared by automatic import stages."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.mission.models import Mission
from app.mission.planning.models import ItineraryAR
from app.mission.planning.types import PlanningRecord


class ImportIssue(PlanningRecord):
    code: str
    message: str
    leg_id: str | None = None
    route_id: str | None = None
    field: str | None = None
    candidates: list[str] = Field(default_factory=list)


class AssociationResult(PlanningRecord):
    assignments: dict[str, str] = Field(default_factory=dict)
    issues: list[ImportIssue] = Field(default_factory=list)
    evidence: dict[str, dict] = Field(default_factory=dict)


class ARResolution(PlanningRecord):
    rows: list[ItineraryAR] = Field(default_factory=list)
    issues: list[ImportIssue] = Field(default_factory=list)
    evidence: dict[str, dict] = Field(default_factory=dict)


class ImportOperation(PlanningRecord):
    id: str
    generation: int = 1
    state: Literal[
        "queued", "running", "needs_input", "ready", "committed", "cancelled", "failed"
    ] = "queued"
    stage: str = "reading_documents"
    mission_id: str
    revision: bool = False
    deadline: datetime
    issues: list[ImportIssue] = Field(default_factory=list)
    error: str | None = None
    details: dict = Field(default_factory=dict)


class RevisionConflict(PlanningRecord):
    field: str
    baseline: object = None
    current: object = None
    incoming: object = None


class RevisionPreview(PlanningRecord):
    mission: Mission
    conflicts: list[RevisionConflict] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    baseline_identity: str = ""
