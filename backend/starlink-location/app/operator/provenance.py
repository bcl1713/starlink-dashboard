"""Backend-owned attribution and trusted source metadata."""

from typing import Literal

from pydantic import Field

from .common import RecordId, SchemaVersion, StrictModel
from .time_models import UtcTimestamp


class Actor(StrictModel):
    """A fixed backend identity and an explicitly unverified display label."""

    backend: str = Field(default="operator_api", min_length=1, max_length=200)
    operator_label: str | None = Field(default=None, max_length=200)


class SourceReference(StrictModel):
    producer_id: str = Field(min_length=1, max_length=200)
    record_id: str | None = Field(default=None, max_length=200)
    revision: str | None = Field(default=None, max_length=200)
    fingerprint: str | None = Field(default=None, max_length=200)


class SourceProvenance(StrictModel):
    kind: Literal["operator_reported", "observed", "modeled"]
    source_mode: Literal["live", "simulation"]
    observed_at: UtcTimestamp | None = None
    predicted_at: UtcTimestamp | None = None
    source_ref: SourceReference | None = None
    mutation_origin: Literal["interactive", "retrospective", "source_sync"] = (
        "interactive"
    )


class StoreHealth(StrictModel):
    schema_version: SchemaVersion = 1
    ready: bool
    store_id: RecordId | None = None
    api_epoch: RecordId | None = None
    source_mode: Literal["live", "simulation"]
    simulation_run_id: str | None = None
    clock_regression: bool = False
    error_code: str | None = None
