"""Shared speed rule for POIs and route hazard crossings."""


def segment_speed(measured: float, planned: float | None, first: bool) -> float:
    expected = planned or measured
    return (measured + expected) / 2.0 if first else expected
