"""Conditional call continuity uses independent capability, not RF mutation."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.services.pop.continuity import project_call_continuity
from app.services.pop.continuity_models import CapabilitySpan
from app.services.pop.models import PopCrossing, PopForecast, PopTransition

CENTER = datetime(2035, 1, 1, 12, tzinfo=timezone.utc)
START, END = CENTER - timedelta(minutes=10), CENTER + timedelta(minutes=10)


def forecast(*centers, status="ready", revision="r"):
    return PopForecast(
        revision=revision,
        catalog_fingerprint="catalog",
        status=status,
        transitions=tuple(
            PopTransition(
                crossing=PopCrossing(
                    id=f"{revision}-{i}",
                    from_pop_id="a",
                    to_pop_id="b",
                    segment_index=0,
                    fraction=0.5,
                    latitude=0,
                    longitude=0,
                    distance_meters=100,
                ),
                crossing_utc=c,
                window_start_utc=c - timedelta(minutes=5),
                window_end_utc=c + timedelta(minutes=5),
            )
            for i, c in enumerate(centers)
        ),
    )


def span(**kwargs):
    return CapabilitySpan(
        **{
            "start_utc": START,
            "end_utc": END,
            "ka": "unavailable",
            "x": "unavailable",
            "starshield": "available",
            "x_concurrency_only": False,
            "existing_call_outage": False,
            "source_ids": ("physical-1",),
        }
        | kwargs
    )


@pytest.fixture
def sole_starshield():
    return {
        "forecast": forecast(CENTER),
        "capabilities": (span(),),
        "start_utc": START,
        "end_utc": END,
    }


def test_sole_starshield_counts_full_window(sole_starshield):
    result = project_call_continuity(**sole_starshield)
    assert result.planned_communications_outage_seconds == 600
    assert result.pop_call_outage_seconds == 600
    assert result.longest_call_outage_seconds == 600
    assert [
        (i.start_utc, i.end_utc)
        for i in result.intervals
        if i.classification == "planned_outage"
    ] == [(CENTER - timedelta(minutes=5), CENTER + timedelta(minutes=5))]


@pytest.mark.parametrize(
    "change,classification",
    [
        ({"ka": "available"}, "advisory"),
        ({"x": "available"}, "advisory"),
        ({"x_concurrency_only": True}, "x_fallback"),
        ({"ka": "unknown", "x": "available"}, "advisory"),
        ({"ka": "unknown", "x_concurrency_only": True}, "x_fallback"),
    ],
)
def test_known_alternative_prevents_outage(sole_starshield, change, classification):
    sole_starshield["capabilities"] = (span(**change),)
    before = sole_starshield["forecast"].model_dump()
    result = project_call_continuity(**sole_starshield)
    assert result.pop_call_outage_seconds == 0
    assert classification in {i.classification for i in result.intervals}
    assert sole_starshield["forecast"].model_dump() == before
    assert sole_starshield["capabilities"][0] == span(**change)


def test_ka_returns_at_center(sole_starshield):
    sole_starshield["capabilities"] = (
        span(end_utc=CENTER),
        span(start_utc=CENTER, ka="available"),
    )
    result = project_call_continuity(**sole_starshield)
    assert result.pop_call_outage_seconds == 300
    assert result.longest_call_outage_seconds == 300


def test_overlapping_transitions_union_and_preserve_ids(sole_starshield):
    sole_starshield["forecast"] = forecast(CENTER, CENTER + timedelta(minutes=2))
    result = project_call_continuity(**sole_starshield)
    assert result.pop_call_outage_seconds == 720
    assert any(i.transition_ids == ("r-0", "r-1") for i in result.intervals)


def test_existing_outage_has_precedence_and_union_total(sole_starshield):
    sole_starshield["capabilities"] = (
        span(end_utc=CENTER),
        span(
            start_utc=CENTER,
            end_utc=CENTER + timedelta(minutes=8),
            existing_call_outage=True,
        ),
        span(start_utc=CENTER + timedelta(minutes=8)),
    )
    result = project_call_continuity(**sole_starshield)
    assert result.planned_communications_outage_seconds == 780
    assert result.pop_call_outage_seconds == 300
    assert result.longest_call_outage_seconds == 780
    assert {"physical-1"} <= set(result.intervals[2].source_ids)


@pytest.mark.parametrize(
    "change", [{"ka": "unknown"}, {"x": "unknown"}, {"starshield": "unknown"}]
)
def test_unknown_is_unresolved(sole_starshield, change):
    sole_starshield["capabilities"] = (span(**change),)
    result = project_call_continuity(**sole_starshield)
    assert result.pop_call_outage_seconds == 0
    assert "unknown" in {i.classification for i in result.intervals}


def test_missing_capability_and_unavailable_forecast_are_unresolved(sole_starshield):
    sole_starshield["capabilities"] = ()
    assert {
        i.classification for i in project_call_continuity(**sole_starshield).intervals
    } == {"unknown"}
    sole_starshield["forecast"] = forecast(status="unavailable")
    sole_starshield["capabilities"] = (span(),)
    assert {
        i.classification for i in project_call_continuity(**sole_starshield).intervals
    } == {"unknown"}


def test_disabled_forecast_keeps_existing_outages_only(sole_starshield):
    sole_starshield["forecast"] = forecast(status="disabled")
    sole_starshield["capabilities"] = (span(existing_call_outage=True),)
    result = project_call_continuity(**sole_starshield)
    assert result.planned_communications_outage_seconds == 1200
    assert result.pop_call_outage_seconds == 0


def test_clip_to_flight_without_mutating_canonical_window(sole_starshield):
    sole_starshield["start_utc"] = CENTER
    assert project_call_continuity(**sole_starshield).pop_call_outage_seconds == 300
    assert sole_starshield["forecast"].transitions[
        0
    ].window_start_utc == CENTER - timedelta(minutes=5)


@pytest.mark.parametrize("invalid", ["bounds", "revision", "overlap", "window"])
def test_invalid_inputs_fail_closed(sole_starshield, invalid):
    if invalid == "bounds":
        sole_starshield["end_utc"] = START
    elif invalid == "revision":
        sole_starshield["forecast"] = forecast(CENTER, revision="")
    elif invalid == "overlap":
        sole_starshield["capabilities"] = (span(), span(ka="available"))
    else:
        f = sole_starshield["forecast"]
        t = f.transitions[0].model_copy(update={"window_end_utc": CENTER})
        sole_starshield["forecast"] = f.model_copy(update={"transitions": (t,)})
    with pytest.raises(ValueError):
        project_call_continuity(**sole_starshield)


def test_capability_rejects_invalid_and_naive_times():
    with pytest.raises(ValidationError):
        span(end_utc=START)
    with pytest.raises(ValidationError):
        span(start_utc=START.replace(tzinfo=None))


def test_unknown_all_service_evidence_cannot_claim_ordinary_connectivity(
    sole_starshield,
):
    sole_starshield["forecast"] = forecast()
    sole_starshield["capabilities"] = (
        span(ka="unknown", x="unknown", starshield="unknown"),
    )
    result = project_call_continuity(**sole_starshield)
    assert {i.classification for i in result.intervals} == {"unknown"}
