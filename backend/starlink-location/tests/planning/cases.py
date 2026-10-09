"""Synthetic records; no operational documents or shared stores."""


def anchor_fields(**changes):
    return {
        "route_id": "route-owned",
        "content_hash": "a" * 64,
        "segment_index": 0,
        "fraction": 0.5,
        "occurrence_id": "occurrence-1",
        "source_time": "2026-10-25T12:00:30Z",
        "latitude": 35.0,
        "longitude": 179.5,
        "timing_mode": "route_bound",
        **changes,
    }


def expected_leg_fields(**changes):
    return {
        "id": "expected-1",
        "ordinal": 1,
        "departure_airport": "AAAA",
        "arrival_airport": "BBBB",
        "departure_time": "2026-10-25T12:00:00Z",
        "arrival_time": "2026-10-25T14:00:00Z",
        **changes,
    }


def ar_fields(**changes):
    return {
        "id": "ar-1",
        "track": "SYNTHETIC",
        "source_page": 1,
        "source_row": 3,
        "source_text": "SYNTHETIC 12:10 12:20 210",
        "entry_time": "2026-10-25T12:10:00Z",
        "exit_time": "2026-10-25T12:20:00Z",
        "source_time_precision": "minute",
        "source_altitude": 210,
        **changes,
    }
