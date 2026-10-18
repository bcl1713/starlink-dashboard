"""Common payload fields shared without importing payload unions."""

from pydantic import Field, field_validator
from .common import Identifier, SchemaVersion, StrictModel


class PayloadBase(StrictModel):
    schema_version: SchemaVersion = 1
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=8000)
    previous_leg_id: Identifier | None = None
    next_leg_id: Identifier | None = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value
