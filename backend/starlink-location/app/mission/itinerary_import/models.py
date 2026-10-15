"""Strict contracts shared by automatic import stages."""

from pydantic import Field

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
