"""Observed-rate adapters and bounded, mask-preserving regional XYZ tiles."""

import argparse
import io
import json
import math
import resource
import time
from dataclasses import dataclass, replace
from pathlib import Path

import h5py
import numpy as np
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds, from_origin
from rasterio.warp import reproject, transform

from .capture import MIB, utc
from .model import Snapshot, TileKey, TilePair, digest, load_capture, write_capture

MAX_LATITUDE = 85.05112878
HALF_WORLD = 20037508.342789244
THRESHOLDS = [0.1, 0.5, 1, 2, 5, 10, 20, 50]
COLORS = np.array(
    [
        [0, 0, 0, 0],
        [185, 225, 255, 220],
        [150, 205, 255, 220],
        [110, 180, 255, 220],
        [70, 145, 245, 220],
        [40, 100, 220, 220],
        [25, 65, 190, 220],
        [15, 40, 155, 220],
        [10, 20, 115, 220],
    ],
    dtype="uint8",
)


@dataclass(frozen=True)
class RadarRaster:
    values: np.ndarray
    valid: np.ndarray
    transform: object
    crs: CRS


def text(value):
    return value.decode() if isinstance(value, bytes) else str(value)


def open_raster(snapshot: Snapshot) -> RadarRaster:
    if snapshot.source == "mrms":
        with rasterio.Env(GDAL_CACHEMAX=32 * MIB), rasterio.open(
            snapshot.local_path
        ) as source:
            tags = source.tags(1)
            if tags.get("GRIB_ELEMENT") != "PrecipRate" or tags.get(
                "GRIB_UNIT"
            ) not in ("[mm/hr]", "[mm/h]"):
                raise ValueError("unexpected observed rain-rate product or units")
            if tags.get("GRIB_FORECAST_SECONDS") != "0":
                raise ValueError("forecast product refused")
            if int(tags.get("GRIB_VALID_TIME", "0")) != snapshot.observed_utc:
                raise ValueError("source timestamp mismatch")
            if source.width * source.height * 5 > 256 * MIB or source.crs is None:
                raise ValueError("raster decode limit or missing CRS")
            values = source.read(1, out_dtype="float32")
            valid = np.isfinite(values) & (values >= 0)
            return RadarRaster(
                np.where(valid, values, 0).astype("float32"),
                valid,
                source.transform,
                source.crs,
            )
    if snapshot.source != "opera":
        raise ValueError("raw source required")
    with h5py.File(snapshot.local_path, "r", rdcc_nbytes=MIB) as source:
        what = source["what"].attrs
        if (
            text(what["object"]) != "COMP"
            or utc(text(what["date"]) + text(what["time"]), "%Y%m%d%H%M%S")
            != snapshot.observed_utc
        ):
            raise ValueError("composite timestamp mismatch")
        data = source["dataset1/data1/data"]
        attrs = source["dataset1/data1/what"].attrs
        where = source["where"].attrs
        if text(attrs["quantity"]) != "RATE":
            raise ValueError("instantaneous rain rate required")
        if data.size * 5 > 256 * MIB or data.shape != (
            int(where["ysize"]),
            int(where["xsize"]),
        ):
            raise ValueError("raster decode limit or dimensions")
        raw = np.empty(data.shape, dtype="float32")
        data.read_direct(raw)
        undetect = raw == attrs["undetect"]
        valid = np.isfinite(raw) & (raw != attrs["nodata"])
        values = raw * float(attrs["gain"]) + float(attrs["offset"])
        values[undetect] = 0
        valid &= values >= 0
        values[~valid] = 0
        crs = CRS.from_string(text(where["projdef"]))
        xs, ys = transform(
            "EPSG:4326", crs, [float(where["UL_lon"])], [float(where["UL_lat"])]
        )
        projection = from_origin(
            xs[0], ys[0], float(where["xscale"]), float(where["yscale"])
        )
        return RadarRaster(values, valid, projection, crs)


def tile_bounds(key: TileKey):
    step = 2 * HALF_WORLD / 2**key.z
    return (
        -HALF_WORLD + key.x * step,
        HALF_WORLD - (key.y + 1) * step,
        -HALF_WORLD + (key.x + 1) * step,
        HALF_WORLD - key.y * step,
    )


def region_keys(latitude, longitude, zoom):
    if (
        not math.isfinite(latitude)
        or abs(latitude) > MAX_LATITUDE
        or not math.isfinite(longitude)
    ):
        raise ValueError("outside Mercator latitude")
    count = 2**zoom
    longitude = (longitude + 180) % 360 - 180
    x = int((longitude + 180) / 360 * count) % count
    y = min(
        count - 1,
        max(
            0,
            int(
                (1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * count
            ),
        ),
    )
    return tuple(
        sorted(
            {
                TileKey(zoom, (x + dx) % count, max(0, min(count - 1, y + dy)))
                for dx in (-1, 0, 1, 2)
                for dy in (-1, 0)
            }
        )
    )


def region(raster):
    # Choose a substantial precipitation patch, rather than one anomalous pixel.
    rows, cols = raster.values.shape
    stride = min(32, rows, cols)
    h, w = rows // stride * stride, cols // stride * stride
    rainy = (raster.values[:h, :w] >= 1) & raster.valid[:h, :w]
    scores = rainy.reshape(h // stride, stride, w // stride, stride).mean(axis=(1, 3))
    if scores.max() == 0:
        return None
    row, col = np.unravel_index(scores.argmax(), scores.shape)
    x, y = raster.transform * (col * stride + stride / 2, row * stride + stride / 2)
    lon, lat = transform(raster.crs, "EPSG:4326", [x], [y])
    return {
        "latitude": lat[0],
        "longitude": lon[0],
        "rain_fraction": float(scores[row, col]),
    }


def render(
    raster: RadarRaster,
    snapshot: Snapshot,
    keys: tuple[TileKey, ...],
    destination: Path,
    *,
    storage_root=None,
):
    pairs = {}
    if len(set(keys)) > 40:
        raise ValueError("only baseline plus three eight-tile regional levels")
    for key in keys:
        values = np.zeros((512, 512), dtype="float32")
        valid = np.zeros((512, 512), dtype="uint8")
        options = {
            "src_transform": raster.transform,
            "src_crs": raster.crs,
            "dst_transform": from_bounds(*tile_bounds(key), 512, 512),
            "dst_crs": "EPSG:3857",
            "resampling": Resampling.nearest,
            "num_threads": 1,
            "warp_mem_limit": 32,
        }
        reproject(raster.values, values, **options)
        reproject(raster.valid.astype("uint8"), valid, **options)
        rgba = COLORS[np.digitize(values, THRESHOLDS)]
        rgba[valid == 0] = 0
        absence = np.zeros((512, 512, 4), dtype="uint8")
        absence[:, :, 3] = np.where(valid != 0, 0, 255)
        directory = destination / snapshot.identity / str(key.z) / str(key.x)
        directory.mkdir(parents=True, exist_ok=True)
        paths = [directory / f"{key.y}-{kind}.png" for kind in ("radar", "absence")]
        from .storage import atomic_write

        for path, pixels in zip(paths, (rgba, absence)):
            encoded = io.BytesIO()
            Image.fromarray(pixels).save(encoded, format="PNG")
            data = encoded.getvalue()
            if len(data) > 2 * MIB:
                raise ValueError("PNG limit")
            atomic_write(path, data, root=storage_root or destination)
        pairs[key] = TilePair(snapshot.identity, *paths, *(digest(p) for p in paths))
    return pairs


def generate(
    snapshot: Snapshot, keys: tuple[TileKey, ...], destination: Path
) -> dict[TileKey, TilePair]:
    return render(open_raster(snapshot), snapshot, keys, destination)


def main(root):
    captures = load_capture(root / "capture.json")
    metadata = dict(captures.metadata)
    metadata["generation"] = {}
    tiles = dict(captures.tiles)
    snapshots = []
    for snapshot in captures.snapshots:
        if snapshot.source == "rainviewer":
            snapshots.append(snapshot)
            continue
        started, cpu = time.perf_counter(), time.process_time()
        raster = open_raster(snapshot)
        snapshot = replace(snapshot, crs=raster.crs.to_string())
        snapshots.append(snapshot)
        cold = {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": time.process_time() - cpu,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        }
        chosen = region(raster)
        metadata["regions"][snapshot.source] = chosen
        if chosen is None:
            metadata["generation"][snapshot.source] = {
                "status": "no precipitation",
                "cold": cold,
            }
            continue
        keys = tuple(TileKey(2, x, y) for x in range(4) for y in range(4))
        for level in (5, 6, 7):
            keys += region_keys(chosen["latitude"], chosen["longitude"], level)
        started, cpu = time.perf_counter(), time.process_time()
        tiles[snapshot.identity] = render(raster, snapshot, keys, root)
        output_bytes = sum(
            p.stat().st_size
            for pair in tiles[snapshot.identity].values()
            for p in (pair.radar_path, pair.absence_path)
        )
        metadata["generation"][snapshot.source] = {
            "status": "measured",
            "observed_utc": snapshot.observed_utc,
            "crs": snapshot.crs,
            "resolution": list(raster.transform)[:6],
            "input_bytes": snapshot.local_path.stat().st_size,
            "output_bytes": output_bytes,
            "cold": cold,
            "warm": {
                "wall_seconds": time.perf_counter() - started,
                "cpu_seconds": time.process_time() - cpu,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * 1024,
            },
            "tile_pairs": len(keys),
        }
        del raster
    metadata["palette"] = {
        "thresholds_mm_per_hour": THRESHOLDS,
        "colors_rgba": COLORS.tolist(),
    }
    write_capture(
        replace(captures, snapshots=tuple(snapshots), tiles=tiles, metadata=metadata)
    )
    (root / "generation.json").write_text(
        json.dumps(metadata["generation"], indent=2) + "\n"
    )
    print(json.dumps(metadata["generation"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    main(parser.parse_args().root)
