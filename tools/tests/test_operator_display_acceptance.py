"""The display proof's synthetic GRIB ranges are admitted by the real parser."""

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_display_source_ranges_match_exact_grib_bytes(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "operator_display", ROOT / "tools/acceptance/operator-display/run.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    hashes = runner.synthetic_sources(tmp_path / "source")
    from app.models.aviation_grid import SourceRef
    from app.services.aviation_weather.gfs.inventory import select_ranges
    from tests.fixtures.gfs_fields import RUN

    ranges = select_ranges(
        (tmp_path / "source/source.idx").read_bytes(),
        SourceRef("fixture", '"version"', 539601570),
        RUN,
        21600,
        (50000,),
    )
    assert {item.quantity for item in ranges} == {"u", "v", "t", "sp"}
    for item in ranges:
        body = (tmp_path / f"source/{item.quantity}.grib2").read_bytes()
        assert item.end - item.start + 1 == len(body)
        assert hashlib.sha256(body).hexdigest() == hashes[f"{item.quantity}.grib2"]
