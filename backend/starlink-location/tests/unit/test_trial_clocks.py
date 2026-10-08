"""Customer clocks must retain exact boundaries and each leg's own T-zero."""

from datetime import datetime

import pytest

from tests.unit.customer_briefing_fixtures import fixture, snapshot, utc


def test_et_midnight_dst_and_per_leg_tzero():
    from app.mission.exporter.trial_clocks import format_clocks
    from app.mission.exporter.trial_projection import project_trial_leg

    for case in fixture("f07")["cases"]:
        start, end = utc(case["takeoff"]), utc(case["landing"])
        assert format_clocks(start, start).et == case["et_start"]
        clocks = format_clocks(end, start)
        assert clocks.et == case["et_end"]
        assert clocks.zulu == case["landing"].replace("T", " ").replace(":00Z", "Z")
        assert clocks.relative == "T+00:30"
    total = 0
    for data in fixture("f08")["legs"]:
        leg = project_trial_leg(snapshot(data))
        start, end = leg.utc_bounds
        assert format_clocks(start, start).relative == "T+00:00"
        total += (end - start).total_seconds()
        outage = next(i for i in leg.intervals if i.decisions[1].value == "Down")
        assert format_clocks(outage.start_time, start).relative == "T+00:20"
    assert total == 21 * 3600  # 1h + 4h + 16h, no ground time.


@pytest.mark.parametrize(
    "instant, et, zulu, relative",
    [
        (
            "2026-10-07T08:00:30Z",
            "2026-10-07 04:00:30 EDT",
            "2026-10-07 08:00:30Z",
            "T+00:00:30",
        ),
        (
            "2026-10-07T07:59:30Z",
            "2026-10-07 03:59:30 EDT",
            "2026-10-07 07:59:30Z",
            "T-00:00:30",
        ),
        (
            "2026-10-07T08:00:00.125Z",
            "2026-10-07 04:00:00.125 EDT",
            "2026-10-07 08:00:00.125Z",
            "T+00:00:00.125",
        ),
        (
            "2026-10-08T10:00:00Z",
            "2026-10-08 06:00 EDT",
            "2026-10-08 10:00Z",
            "T+26:00",
        ),
    ],
)
def test_exact_seconds_tminus_and_long_elapsed(instant, et, zulu, relative):
    from app.mission.exporter.trial_clocks import format_clocks

    labels = format_clocks(utc(instant), utc("2026-10-07T08:00:00Z"))
    assert (labels.et, labels.zulu, labels.relative) == (et, zulu, relative)


def test_elapsed_uses_utc_across_repeated_local_hour():
    from zoneinfo import ZoneInfo

    from app.mission.exporter.trial_clocks import format_clocks

    zone = ZoneInfo("America/New_York")
    start = datetime(2026, 11, 1, 1, 50, tzinfo=zone, fold=0)
    end = datetime(2026, 11, 1, 1, 20, tzinfo=zone, fold=1)
    assert format_clocks(end, start).relative == "T+00:30"


def test_naive_clocks_rejected():
    from app.mission.exporter.trial_clocks import format_clocks

    with pytest.raises(ValueError, match="timezone"):
        format_clocks(
            utc("2026-10-07T08:00:00Z").replace(tzinfo=None),
            utc("2026-10-07T08:00:00Z"),
        )
