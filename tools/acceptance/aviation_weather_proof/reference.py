"""Independent geographic CPU reference, with no renderer/normalizer helpers.

Longitude bracketing uses sorted geographic coordinates on three adjacent worlds;
latitude uses sorted geographic nodes. Source checks select exact nodes from
ecCodes coordinate arrays, independently of scan ordering/regridding.
"""

import json
import math
from pathlib import Path

import eccodes as ec
import numpy as np

from .model import CaptureManifest, confined, file_hash, object_path


DEFAULT_GFS_COORDINATES = (
    (-180, 0), (179.5, 10), (-179.5, -10), (0, 89.5), (120, -89.5),
    (0, 90), (-180, -90), (-45, 50), (135, -35), (30, 20),
)


def _bracket(coordinates, query, *, descending=False):
    """Keep an enclosing two-node stencil even when one weight is zero."""
    ordered = sorted(coordinates, reverse=descending)
    for (first, first_index), (second, second_index) in zip(ordered, ordered[1:]):
        enclosed = second < query <= first if descending else first <= query < second
        if enclosed:
            fraction = (query - first) / (second - first)
            return [(first_index, 1 - fraction), (second_index, fraction)]
    # The end of partial coverage or a latitude pole clamps both corners to
    # that boundary node. Full-world longitude has shifted geographic nodes.
    if ordered and query == ordered[-1][0]:
        return [(ordered[-1][1], 1.0), (ordered[-1][1], 0.0)]
    raise ValueError("reference coordinate outside grid coverage")


def sample_grid(descriptor_path: Path, longitude: float, latitude: float) -> dict:
    """Read verified normalized buffers and bracket geographic nodes independently.

    This reusable oracle accepts arbitrary geographic samples for future actual
    shader readback. It never receives browser UV/index calculations as input.
    """
    descriptor_path = Path(descriptor_path)
    descriptor = json.loads(descriptor_path.read_text())
    if descriptor["schema"] != "aviation-weather-v1" or descriptor["representation"] != "latlon-grid-v1":
        raise ValueError("unsupported reference schema")
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("invalid reference geographic coordinate")
    grid = descriptor["grid"]
    width, height = grid["width"], grid["height"]
    base_lons = [grid["longitude_start"] + i * grid["longitude_step"] for i in range(width)]
    lats = [(grid["latitude_start"] + i * grid["latitude_step"], i) for i in range(height)]
    # Geographic equivalence, not an integer longitude-to-texture formula.
    longitude = math.remainder(longitude, 360)
    if longitude < base_lons[0]:
        longitude += 360
    if longitude >= base_lons[0] + 360:
        longitude -= 360
    full_longitude = math.isclose(width * grid["longitude_step"], 360)
    if (not full_longitude and not base_lons[0] <= longitude <= base_lons[-1]) or not min(coordinate for coordinate, _ in lats) <= latitude <= max(coordinate for coordinate, _ in lats):
        return {"longitude": longitude, "latitude": latitude, "mask": 1,
                "values": {name: None for name in descriptor["components"]}, "contributors": []}
    shifts = (-360, 0, 360) if full_longitude else (0,)
    candidates = [(coordinate + shift, index) for shift in shifts for index, coordinate in enumerate(base_lons)]
    xs = _bracket(candidates, longitude)
    ys = _bracket(lats, latitude, descending=grid["latitude_step"] < 0)
    arrays = {}
    for name, item in {**descriptor["components"], "mask": descriptor["mask"]}.items():
        path = confined(descriptor_path.parent, item["path"])
        if path.stat().st_size != item["byte_size"] or file_hash(path) != item["sha256"]:
            raise ValueError("reference artifact changed")
        array = np.fromfile(path, dtype="u1" if name == "mask" else "<i2")
        if len(array) != width * height:
            raise ValueError("reference payload dimension mismatch")
        arrays[name] = array.reshape(height, width)
    stencil = [(y, x, wy * wx) for y, wy in ys for x, wx in xs]
    masks = [int(arrays["mask"][y, x]) for y, x, _ in stencil]
    invalid = next((value for value in masks if value != 0), 0)
    contributing = [(y, x, weight) for y, x, weight in stencil if weight > 0]
    values = {}
    for name, declaration in descriptor["components"].items():
        values[name] = None if invalid else sum(
            (declaration["offset"] + declaration["scale"] * int(arrays[name][y, x])) * weight
            for y, x, weight in contributing
        )
    return {"longitude": longitude, "latitude": latitude, "mask": invalid, "values": values,
            "contributors": [{"longitude": base_lons[x], "latitude": lats[y][0], "weight": weight} for y, x, weight in contributing]}


def compare_gfs(capture: CaptureManifest, descriptor_path: Path, coordinates=DEFAULT_GFS_COORDINATES) -> list[dict]:
    """Retain exact source-node comparisons; non-source-node queries fail explicitly.

    These controls deliberately coincide with output and source nodes, so source
    resampling tolerance is zero. Quantization tolerance is half a declared step.
    Off-node renderer controls use sample_grid without claiming source equality.
    """
    descriptor = json.loads(Path(descriptor_path).read_text())
    records = [{"longitude": lon, "latitude": lat, "source_values": {}, "source_coordinates": {},
                "source_metadata": {}, "source_hashes": {}, "normalized_values": sample_grid(descriptor_path, lon, lat)["values"],
                "normalized_mask": sample_grid(descriptor_path, lon, lat)["mask"],
                "resampling_tolerance": {}, "resampling_error": {}, "quantization_tolerance": {}, "absolute_error": {}}
               for lon, lat in coordinates]
    for obj in capture.objects:
        with object_path(capture, obj).open("rb", buffering=0) as stream:
            if stream.read(4) != b"GRIB":
                continue
            stream.seek(0)
            handle = ec.codes_grib_new_from_file(stream)
            if handle is None:
                raise ValueError("reference source message absent")
            try:
                name = ec.codes_get(handle, "shortName")
                metadata = {key: ec.codes_get(handle, key) for key in ("gridType", "Ni", "Nj", "units", "typeOfLevel", "level", "dataDate", "dataTime", "endStep", "validityDate", "validityTime", "iScansNegatively", "jScansPositively", "uvRelativeToGrid")}
                source_lats = ec.codes_get_array(handle, "latitudes")
                source_lons = ec.codes_get_array(handle, "longitudes")
                source_values = ec.codes_get_values(handle)
                for record in records:
                    # Geodesic nearest-point routines can pick ANY longitude at
                    # a pole. Preserve the exact declared node longitude.
                    delta_lon = np.abs(source_lons - record["longitude"])
                    equivalent_lon = np.minimum(delta_lon, np.abs(delta_lon - 360))
                    matches = np.flatnonzero((equivalent_lon < 1e-7) & (np.abs(source_lats - record["latitude"]) < 1e-7))
                    if len(matches) != 1:
                        raise ValueError("source oracle control must be an exact unique source node")
                    index = int(matches[0])
                    value = float(source_values[index])
                    normalized = record["normalized_values"][name]
                    if record["normalized_mask"] != 0 or normalized is None:
                        raise ValueError("source comparison control is missing")
                    error = abs(value - normalized)
                    tolerance = descriptor["components"][name]["scale"] / 2
                    if error > tolerance + 1e-9:
                        raise ValueError("independent source/reference mismatch")
                    record["source_values"][name] = value
                    record["source_coordinates"][name] = {"longitude": float(source_lons[index]), "latitude": float(source_lats[index]), "source_index": index}
                    record["source_metadata"][name] = metadata
                    record["source_hashes"][name] = obj.sha256
                    record["absolute_error"][name] = error
                    record["resampling_error"][name] = 0.0
                    record["resampling_tolerance"][name] = 0.0
                    record["quantization_tolerance"][name] = tolerance
            finally:
                ec.codes_release(handle)
    if any(set(record["source_values"]) != {"u", "v", "t"} for record in records):
        raise ValueError("independent source controls incomplete")
    return records
