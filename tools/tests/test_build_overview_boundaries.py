"""Exercise source conversion with real, small Natural Earth-like shapefiles."""

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import shapefile

spec = importlib.util.spec_from_file_location(
    "build_overview_boundaries",
    Path(__file__).resolve().parents[1] / "build-overview-boundaries.py",
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def archive(path, points, classification, *, boundary=True):
    streams = [io.BytesIO() for _ in range(3)]
    with shapefile.Writer(
        shp=streams[0], shx=streams[1], dbf=streams[2], shapeType=shapefile.POLYLINE
    ) as writer:
        writer.field("FEATURECLA" if boundary else "featurecla", "C")
        if boundary:
            writer.field("TYPE", "C")
        writer.line([points])
        writer.record(*([classification, "Land"] if boundary else [classification]))
    with zipfile.ZipFile(path, "w") as output:
        for extension, stream in zip(("shp", "shx", "dbf"), streams):
            output.writestr(f"fixture.{extension}", stream.getvalue())
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BoundaryConversionTests(unittest.TestCase):
    def test_country_asset_contains_solid_closed_coastline_and_disputed_land_border(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            island = [[-156, 20], [-155, 20], [-155, 21], [-156, 20]]
            hashes = {
                "countries": archive(
                    root / "countries.zip", [[10, 10], [11, 10]], "Disputed"
                ),
                "coastlines": archive(
                    root / "coastlines.zip", island, "Coastline", boundary=False
                ),
                "subdivisions": archive(
                    root / "subdivisions.zip", [[20, 20], [21, 20]], "Admin-1"
                ),
            }
            with (
                patch.object(builder, "SOURCES", hashes),
                patch(
                    "sys.argv",
                    [
                        "build-overview-boundaries.py",
                        "--input-dir",
                        str(root),
                        "--output-dir",
                        str(root / "output"),
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                builder.main()
            countries = json.loads((root / "output/countries.json").read_text())
            self.assertEqual(
                countries,
                {
                    "version": 1,
                    "lines": [
                        {"disputed": True, "points": [[10, 10], [11, 10]]},
                        {"disputed": False, "points": island},
                    ],
                },
            )
            subdivisions = json.loads((root / "output/subdivisions.json").read_text())
            self.assertEqual(
                subdivisions["lines"],
                [
                    {"disputed": False, "points": [[20, 20], [21, 20]]},
                ],
            )
            self.assertFalse((root / "output/coastlines.json").exists())

    def test_unverified_coastline_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "coastlines.zip"
            archive(source, [[0, 0], [1, 0]], "Coastline", boundary=False)
            with self.assertRaisesRegex(ValueError, "Unrecognized dataset archive"):
                builder.convert(source, "untrusted")


if __name__ == "__main__":
    unittest.main()
