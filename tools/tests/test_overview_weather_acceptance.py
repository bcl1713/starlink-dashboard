"""Behavioral gates for the exact-candidate weather acceptance harness."""

import importlib.util
import struct
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/acceptance/overview-weather/run.sh"


def test_check_validates_without_docker_or_browser():
    result = subprocess.run(
        ["bash", str(RUNNER), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_runner_rejects_non_exact_candidate_before_docker():
    result = subprocess.run(
        ["bash", str(RUNNER), "dev"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "exact 40-hex" in result.stderr


def test_provider_png_independent_landmark_colors():
    path = ROOT / "tools/acceptance/overview-weather/provider_fixture.py"
    spec = importlib.util.spec_from_file_location("weather_provider", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    png = module.tile_png(2, 1, coverage=False)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (512, 512)
    offset, compressed = 8, b""
    while offset < len(png):
        size = struct.unpack(">I", png[offset : offset + 4])[0]
        kind = png[offset + 4 : offset + 8]
        if kind == b"IDAT":
            compressed += png[offset + 8 : offset + 8 + size]
        offset += size + 12
    raw = zlib.decompress(compressed)
    assert raw[1:5] == bytes([255, 40, 40, 220])  # independently chosen northeast red
    coverage = module.tile_png(0, 0, coverage=True)
    assert coverage != png


def test_provider_distinguishes_mercator_latitude_rows_and_longitude_edges():
    path = ROOT / "tools/acceptance/overview-weather/provider_fixture.py"
    spec = importlib.util.spec_from_file_location("weather_landmarks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.tile_png(2, 0) != module.tile_png(2, 1)
    assert module.tile_png(2, 1) != module.tile_png(3, 1)
    assert module.tile_png(1, 1) != module.tile_png(2, 1)
