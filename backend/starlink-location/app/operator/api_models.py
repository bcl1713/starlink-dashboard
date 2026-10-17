"""Public journal DTOs deliberately exclude trusted/internal producer commands."""

from typing import Literal

from pydantic import Field

from .common import SchemaVersion, StrictModel
from .models import AuditNote, PositiveVersion, RecordInput
from .payloads import JournalPayload


class JournalCreate(RecordInput):
    record_type: Literal["journal_entry"]
    payload: JournalPayload
    operator_label: str | None = Field(default=None, max_length=200)


class JournalUpdate(JournalCreate):
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None


class JournalTransition(StrictModel):
    schema_version: SchemaVersion = 1
    expected_version: PositiveVersion
    audit_note: AuditNote | None = None
    operator_label: str | None = Field(default=None, max_length=200)
