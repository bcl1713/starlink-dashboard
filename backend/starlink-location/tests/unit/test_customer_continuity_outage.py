"""Independent outages retain their evidence within overlapping transition windows."""

import json
from dataclasses import replace
from datetime import timedelta

from app.mission.exporter.customer_projection import project_briefing_leg
from app.mission.exporter.customer_view import project_customer_leg
from app.mission.exporter.snapshot_inputs import canonical_json
from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan
from app.services.pop.models import PopForecast
from tests.unit.test_customer_continuity import captured_projection


def test_existing_outage_and_overlapping_transitions_keep_union_and_physical_causes():
    captured, _, _, _ = captured_projection()
    leg = captured.legs[0]
    start, end = leg.utc_bounds
    a, b = start + timedelta(minutes=27), start + timedelta(minutes=32)
    raw = json.loads(leg.timeline_json)
    spans = [
        CapabilitySpan(
            start_utc=start,
            end_utc=a,
            ka="unavailable",
            x="unavailable",
            starshield="available",
        ),
        CapabilitySpan(
            start_utc=a,
            end_utc=b,
            ka="unavailable",
            x="unavailable",
            starshield="unavailable",
            existing_call_outage=True,
            source_ids=("independent-outage",),
        ),
        CapabilitySpan(
            start_utc=b,
            end_utc=end,
            ka="unavailable",
            x="unavailable",
            starshield="available",
        ),
    ]
    continuity = project_call_continuity(
        PopForecast.model_validate(raw["pop_forecast"]),
        spans,
        start_utc=start,
        end_utc=end,
    )
    raw["call_continuity"] = continuity.model_dump(mode="json")
    sources = tuple(
        canonical_json(
            {
                "source_id": f"real-{t}",
                "source_type": "configured_outage",
                "transport": t,
                "state": "offline",
                "start_time": a.isoformat(),
                "end_time": b.isoformat(),
                "reason": "Independent outage",
            }
        )
        for t in ("Ka", "Ku", "X")
    )
    leg = replace(
        leg,
        timeline_json=canonical_json(raw),
        source_records=leg.source_records + sources,
    )
    projection = project_briefing_leg(leg)
    view = project_customer_leg(leg, projection, leg_number=1, leg_count=1)
    existing = next(
        i for i in projection.intervals if i.call_classification == "existing_outage"
    )
    assert existing.call_source_ids == ("independent-outage",)
    assert all(d.value == "Down" for d in existing.decisions)
    assert {"real-Ka", "real-Ku", "real-X"} <= set(existing.active_source_ids)
    assert any(
        "All transports unavailable" in r.impact
        and "Starshield Transition Window" in r.impact
        for r in view.rows
    )
    assert continuity.planned_communications_outage_seconds == 600
    assert continuity.pop_call_outage_seconds == 300
    assert continuity.longest_call_outage_seconds == 600
