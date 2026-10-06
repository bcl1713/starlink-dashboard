"""Inventory selection cannot invent fields, runs or validity."""

from datetime import datetime, timezone

import pytest

from app.models.aviation_grid import SourceRef

RUN = int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp() * 1000)
INDEX = b"1:0:d=2026100600:TMP:500 mb:6 hour fcst:\n2:8:d=2026100600:UGRD:500 mb:6 hour fcst:\n3:16:d=2026100600:VGRD:500 mb:6 hour fcst:\n4:24:d=2026100600:PRES:surface:6 hour fcst:\n"


def test_selects_complete_triplet_and_surface_ranges():
    from app.services.aviation_weather.gfs.inventory import select_ranges

    result = select_ranges(
        INDEX, SourceRef("gfs.file", '"v1"', 32), RUN, 21600, (50000,)
    )
    assert [(x.quantity, x.start, x.end, x.pressure_pa) for x in result] == [
        ("t", 0, 7, 50000),
        ("u", 8, 15, 50000),
        ("v", 16, 23, 50000),
        ("sp", 24, 31, None),
    ]


@pytest.mark.parametrize(
    "index",
    [
        INDEX.replace(b"2:8:", b"2:0:"),
        INDEX.replace(b":UGRD:", b":TMP:"),
        INDEX.replace(b":surface:", b":mean sea level:"),
        INDEX.replace(b"d=2026100600", b"d=2026100612"),
        INDEX.replace(b"6 hour fcst", b"3 hour fcst"),
        INDEX.replace(b"4:24:", b"4:33:"),
        b"x" * (1024**2 + 1),
    ],
    ids=["offset", "duplicate", "surface", "run", "lead", "bounds", "oversized"],
)
def test_invalid_inventory_cannot_select_a_partial_grid(index):
    from app.services.aviation_weather.gfs.inventory import select_ranges

    with pytest.raises(ValueError):
        select_ranges(index, SourceRef("gfs.file", '"v1"', 32), RUN, 21600, (50000,))


def test_nearest_time_ties_earlier_and_refuses_outside_horizon():
    from app.services.aviation_weather.gfs.inventory import select_time

    assert select_time(RUN, (0, 10800, 21600), RUN + 16200000) == 10800
    assert select_time(RUN, (0, 10800), RUN - 1) is None
    assert select_time(RUN, (0, 10800), RUN + 172800001) is None


def test_cycle_discovery_uses_actual_prefixes():
    from app.services.aviation_weather.gfs.inventory import discover_runs

    body = b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><CommonPrefixes><Prefix>gfs.20261006/00/</Prefix></CommonPrefixes><IsTruncated>false</IsTruncated></ListBucketResult>'
    assert discover_runs(body) == (RUN,)
    with pytest.raises(ValueError):
        discover_runs(body.replace(b"/00/", b"/17/"))


def test_listing_rejects_entities_and_oversized_metadata():
    from app.services.aviation_weather.gfs.inventory import discover_runs

    for body in (b'<!DOCTYPE x [<!ENTITY a "xxx">]><x>&a;</x>', b"x" * (1024**2 + 1)):
        with pytest.raises(ValueError):
            discover_runs(body)
