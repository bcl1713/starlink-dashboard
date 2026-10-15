"""Display clocks must not round geometry or understate risk."""

import importlib
from datetime import datetime

import pytest

from tests.unit.customer_briefing_fixtures import utc


def formatter():
    name = "app.mission.exporter.customer_clocks"
    assert importlib.util.find_spec(name), "compact customer clock contract is absent"
    return importlib.import_module(name).format_customer_range


def test_customer_range_ordinary_minutes_and_outward_rounding():
    f = formatter()
    dep = utc("2026-10-20T10:00:00Z")
    ordinary = f(dep, utc("2026-10-20T10:15:00Z"), dep)
    assert (ordinary.start, ordinary.end, ordinary.approximate) == (
        "06:00 ET",
        "06:15 ET",
        False,
    )
    start, end = utc("2026-10-20T12:00:30.123456Z"), utc("2026-10-20T12:05:20.654321Z")
    original = (start.isoformat(), end.isoformat())
    result = f(start, end, dep)
    assert (result.start, result.end, result.approximate) == (
        "08:00 ET",
        "08:06 ET",
        True,
    )
    assert (start.isoformat(), end.isoformat()) == original


def test_customer_range_rejects_naive_or_reversed_instants():
    f = formatter()
    dep = utc("2026-10-20T10:00:00Z")
    with pytest.raises(ValueError):
        f(datetime(2026, 10, 20), dep, dep)  # noqa: DTZ001 — rejection case
    with pytest.raises(ValueError):
        f(dep, dep, dep)


@pytest.mark.parametrize("hour,zone", [(5, "EDT"), (6, "EST")])
def test_both_occurrences_of_repeated_fall_back_hour_have_explicit_zone(hour, zone):
    start = utc(f"2026-11-01T0{hour}:00:00Z")
    end = utc(f"2026-11-01T0{hour}:15:00Z")
    result = formatter()(start, end, utc("2026-11-01T05:00:00Z"))
    assert (result.start, result.end, result.approximate) == (
        f"01:00 {zone}",
        f"01:15 {zone}",
        False,
    )
