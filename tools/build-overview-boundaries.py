#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyshp==2.3.1", "shapely==2.1.2"]
# ///
"""Convert verified Natural Earth archives into bounded, offline globe assets.

uv run tools/build-overview-boundaries.py --input-dir /path/to/archives
The input directory must contain countries.zip and subdivisions.zip.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import shapefile
from shapely.geometry import LineString

SOURCES = {
    "countries": "16ead035f539c8b6c23650c5845d86ad3556553e7456bdf9b4730210f26aacbe",
    "subdivisions": "86acd56ce6c0e47f5fa79725591533b5766f26d6ed1437b086f2b8d4028fe456",
}


def convert(archive: Path, expected_hash: str) -> dict:
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError(f"Unrecognized dataset archive: {archive.name}")
    lines = []
    with zipfile.ZipFile(io.BytesIO(raw)) as source:
        stem = next(name[:-4] for name in source.namelist() if name.endswith(".shp"))
        reader = shapefile.Reader(
            shp=io.BytesIO(source.read(stem + ".shp")),
            shx=io.BytesIO(source.read(stem + ".shx")),
            dbf=io.BytesIO(source.read(stem + ".dbf")),
            encoding="utf-8",
        )
        for record in reader.iterShapeRecords():
            attrs = record.record.as_dict()
            classification = attrs["FEATURECLA"]
            if (
                classification in {"Lease limit", "Overlay limit"}
                or attrs["TYPE"] == "Water Indicator"
            ):
                continue
            disputed = any(
                word in classification.lower()
                for word in (
                    "disputed",
                    "indefinite",
                    "indeterminant",
                    "line of control",
                    "unrecognized",
                )
            )
            shape = record.shape
            ends = [*shape.parts[1:], len(shape.points)]
            for start, end in zip(shape.parts, ends):
                # Simplification must see continuous longitude, including the date line.
                unwrapped = []
                for lon, lat in shape.points[start:end]:
                    if unwrapped:
                        lon = (
                            unwrapped[-1][0]
                            + (lon - unwrapped[-1][0] + 180) % 360
                            - 180
                        )
                    unwrapped.append((lon, lat))
                if len(unwrapped) < 2:
                    continue
                simplified = LineString(unwrapped).simplify(
                    0.025, preserve_topology=True
                )
                points = [
                    [round((lon + 180) % 360 - 180, 5), round(lat, 5)]
                    for lon, lat in simplified.coords
                ]
                if len(points) >= 2 and points[0] != points[-1] or len(points) > 2:
                    lines.append({"disputed": disputed, "points": points})
    points_count = sum(len(line["points"]) for line in lines)
    if points_count > 120_000:
        raise ValueError("Dataset exceeds the runtime point budget")
    return {"version": 1, "lines": lines}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "frontend/mission-planner/public/boundaries",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, expected_hash in SOURCES.items():
        data = convert(args.input_dir / f"{name}.zip", expected_hash)
        output = args.output_dir / f"{name}.json"
        output.write_text(
            json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        if output.stat().st_size > 4_000_000:
            raise ValueError("Dataset exceeds the runtime byte budget")
        print(
            f"{name}: {len(data['lines'])} lines, {sum(len(line['points']) for line in data['lines'])} points, {output.stat().st_size} bytes"
        )


if __name__ == "__main__":
    main()
