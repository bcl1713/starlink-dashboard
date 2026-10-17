"""Deterministic, resource-free Operator fixtures."""

from datetime import datetime, timedelta, timezone

import pytest


class FakeClock:
    def __init__(self, now: datetime, monotonic: float = 0.0):
        self.current = now
        self.elapsed = monotonic

    def now(self) -> datetime:
        return self.current

    def monotonic(self) -> float:
        return self.elapsed

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)
        self.elapsed += seconds


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 10, 17, 16, tzinfo=timezone.utc))


@pytest.fixture
def record_data():
    return {
        "schema_version": 1,
        "record_type": "journal_entry",
        "mission_id": "demo-mission",
        "leg_id": None,
        "scope": "mission",
        "time": {
            "occurred_at": "2026-10-17T14:30:00Z",
            "ended_at": "2026-10-17T14:42:00Z",
            "precision": "exact",
            "end_state": "known",
            "planned_start_at": None,
            "planned_end_at": None,
        },
        "payload": {
            "schema_version": 1,
            "entry_type": "note",
            "title": "Synthetic note",
            "note": "Synthetic content",
        },
    }


@pytest.fixture
def service(tmp_path, clock, monkeypatch):
    from app.mission import storage
    from app.operator.models import Actor
    from app.operator.references import MissionReferences
    from app.operator.service import OperatorService
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore
    from tests.operator.service_helpers import save_mission

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    save_mission("demo-mission")
    save_mission("other-mission")
    store = OperatorStore.open(
        OperatorSettings(enabled=True, root=tmp_path / "operator"),
        initialize=True,
        clock=clock,
    )
    yield OperatorService(
        store, clock=clock, actor=Actor(), references=MissionReferences()
    )
    store.close()
