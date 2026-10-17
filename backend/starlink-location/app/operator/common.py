"""Shared strict scalar contracts; no storage or clock side effects."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)


def parse_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        # ValueError becomes a Pydantic field error; TypeError escapes validation.
        raise ValueError("Expected a UUID string")  # noqa: TRY004
    return UUID(value)


RecordId = Annotated[UUID, BeforeValidator(parse_uuid)]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")]
SchemaVersion = Annotated[int, Field(strict=True, ge=1, le=1)]
