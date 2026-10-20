"""Human reports of service transport intentions, application and checks."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .common import Identifier, RecordId, StrictModel
from .payload_base import PayloadBase
from .time_models import UtcTimestamp

TransportValue = Annotated[str, Field(min_length=1, max_length=200)]


class ReportTime(StrictModel):
    at: UtcTimestamp | None = None
    precision: Literal["exact", "approximate", "unknown"] = "unknown"

    @model_validator(mode="after")
    def valid_precision(self):
        if (self.at is None) != (self.precision == "unknown"):
            raise ValueError("Report time and precision must agree")
        return self


class TransportIntent(StrictModel):
    transport_id: Identifier | None = None
    transport: TransportValue = "unknown"


class TransportChangeReport(TransportIntent):
    time: ReportTime = Field(default_factory=ReportTime)


class TransportCheck(StrictModel):
    time: ReportTime = Field(default_factory=ReportTime)
    result: Literal["satisfactory", "issue_reported", "unknown"] = "unknown"
    note: str = Field(default="", max_length=8000)


class TransportServiceRow(StrictModel):
    row_id: RecordId
    service_id: Identifier | None = None
    service: str = Field(min_length=1, max_length=200)
    intended: TransportIntent | None = None
    requested: TransportChangeReport | None = None
    applied: TransportChangeReport | None = None
    checked: TransportCheck | None = None

    @field_validator("service")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Service cannot be blank")
        return value.strip()


class TransportDecisionPayload(PayloadBase):
    entry_type: Literal["transport_decision"] = "transport_decision"
    services: list[TransportServiceRow] = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=1000)
    call_id: RecordId | None = None
    conference_id: RecordId | None = None

    @model_validator(mode="after")
    def unique_rows(self):
        if len({s.row_id for s in self.services}) != len(self.services):
            raise ValueError("Duplicate service row IDs")
        return self
