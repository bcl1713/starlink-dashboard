"""Historical planning references and transport evidence use separate namespaces."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mission.models import MissionLegTimeline
from app.mission.planning.models import LegHistory
from app.mission.planning.sources import source_closure
from app.services.pop.continuity_models import (
    CallContinuityInterval,
    CallContinuityProjection,
)

from . import test_store
from .test_store import bind, create

service = test_store.service


@pytest.mark.parametrize("missing_revision", [False, True])
def test_transport_evidence_does_not_replace_historical_planning_references(
    service, tmp_path, missing_revision
):
    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    start = datetime(2026, 10, 16, tzinfo=timezone.utc)
    timeline = MissionLegTimeline(
        mission_leg_id="historical",
        call_continuity=CallContinuityProjection(
            revision="captured-route",
            intervals=(
                CallContinuityInterval(
                    start_utc=start,
                    end_utc=start + timedelta(minutes=10),
                    classification="ordinary",
                    source_ids=("physical-segment", "X line-of-sight evidence"),
                ),
            ),
            planned_communications_outage_seconds=0,
            pop_call_outage_seconds=0,
            longest_call_outage_seconds=0,
        ),
    )
    history = LegHistory(
        leg=manifest.expected_legs[0].model_copy(deep=True),
        timeline=timeline,
        source_ids=[s.id for s in manifest.source_revisions],
        revision=manifest.revision,
        reason="revision",
    )
    if missing_revision:
        history.source_ids.append("missing-retained-planning-revision")
    manifest.leg_history.append(history)
    before = manifest.model_dump_json()
    if missing_revision:
        with pytest.raises(
            ValueError, match="History references a missing source revision"
        ):
            source_closure(mission, manifest)
    else:
        assert source_closure(mission, manifest) == tuple(manifest.source_revisions)
    assert manifest.model_dump_json() == before
    assert history.timeline.call_continuity.intervals[0].source_ids == (
        "physical-segment",
        "X line-of-sight evidence",
    )
