"""Pressure altitude and conservative vertical interpolation, worker-owned."""

import math
from dataclasses import replace

from app.models.aviation_grid import FLIGHT_LEVELS, GfsSelection

from .decode import DecodedFields


def flight_level_pressure(flight_level: int) -> float:
    if type(flight_level) is not int or flight_level not in FLIGHT_LEVELS:
        raise ValueError("Unsupported GFS flight level")
    height = flight_level * 100 * 0.3048
    exponent = 9.80665 / (287.05287 * 0.0065)
    if height <= 11000:
        return 101325 * (1 - 0.0065 * height / 288.15) ** exponent
    p11 = 101325 * (1 - 0.0065 * 11000 / 288.15) ** exponent
    return p11 * math.exp(-9.80665 * (height - 11000) / (287.05287 * 216.65))


def selected_pressure(selection: GfsSelection) -> float:
    vertical = selection.vertical
    return (
        vertical.pressure_pa
        if vertical.kind == "pressure"
        else flight_level_pressure(vertical.flight_level)
    )


def source_pressures(
    selection: GfsSelection, available_pa: tuple[int, ...]
) -> tuple[int, ...]:
    if any(type(p) is not int or not 0 < p <= 110000 for p in available_pa):
        raise ValueError("Invalid actual pressure inventory")
    target = selected_pressure(selection)
    if selection.vertical.kind == "pressure":
        if target not in available_pa:
            raise ValueError("Selected native pressure absent")
        return (int(target),)
    lower = max((p for p in available_pa if p < target), default=None)
    upper = min((p for p in available_pa if p > target), default=None)
    if lower is None or upper is None:
        raise ValueError("Flight level has no complete actual brackets")
    return lower, upper


def matches_selection(selection, vertical):
    if selection.vertical.kind != vertical.kind:
        return False
    return (
        selection.vertical.pressure_pa == vertical.pressure_pa
        if vertical.kind == "pressure"
        else selection.vertical.flight_level == vertical.flight_level
    )


def interpolate_vertical(fields: DecodedFields, target_pa: float) -> DecodedFields:
    import numpy as np

    pressures = sorted({p for name, p in fields.components if name != "sp"})
    if (
        not math.isfinite(target_pa)
        or len(pressures) != 2
        or not pressures[0] < target_pa < pressures[1]
        or fields.run_at_ms != fields.bundle.run_at_ms
        or fields.lead_seconds != fields.bundle.lead_seconds
    ):
        raise ValueError("Incoherent vertical derivation or extrapolation")
    expected = {(name, p) for p in pressures for name in ("u", "v", "t")} | {
        ("sp", None)
    }
    shape = len(fields.latitudes), len(fields.longitudes)
    if set(fields.components) != expected or any(
        values.shape != shape or validity.shape != shape
        for values, validity in fields.components.values()
    ):
        raise ValueError("Incomplete matching vertical grids")
    surface, surface_valid = fields.components[("sp", None)]
    valid = surface_valid & np.isfinite(surface)
    for values, validity in fields.components.values():
        valid &= validity & np.isfinite(values)
    # An atmospheric target cannot admit an underground bracket contributor.
    terrain = surface_valid & (pressures[1] > surface)
    weight = math.log(target_pa / pressures[0]) / math.log(pressures[1] / pressures[0])
    components = {("sp", None): (surface, surface_valid)}
    for name in ("u", "v", "t"):
        lower = fields.components[(name, pressures[0])][0].astype("f8")
        upper = fields.components[(name, pressures[1])][0]
        values = lower * (1 - weight) + upper * weight
        components[(name, target_pa)] = (values, valid.copy())
    return replace(fields, components=components, terrain=terrain)
