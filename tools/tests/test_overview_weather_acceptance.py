"""Behavioral gates for the exact-candidate weather acceptance harness."""

import asyncio
import importlib.util
import json
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

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


@pytest.mark.asyncio
async def test_provider_advertises_opaque_path_and_rejects_timestamp_tile(tmp_path):
    path = ROOT / "tools/acceptance/overview-weather/provider_fixture.py"
    spec = importlib.util.spec_from_file_location("weather_opaque_paths", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONTROL = tmp_path / "control.json"
    module.EVENTS = tmp_path / "events.jsonl"
    module.CONTROL.write_text(
        json.dumps({"frame": 1791248400, "radar_path": "/v2/radar/f1fa64870793"})
    )

    async def response(host, target):
        reader = asyncio.StreamReader()
        writer = module.Writer(reader, host)
        writer.write(f"GET {target} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
        try:
            await writer.drain()
            return await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    metadata = await response("api.rainviewer.com", "/public/weather-maps.json")
    frame = json.loads(metadata.split(b"\r\n\r\n", 1)[1])["radar"]["past"][0]
    assert frame == {"time": 1791248400, "path": "/v2/radar/f1fa64870793"}
    legacy = await response(
        "tilecache.rainviewer.com", "/v2/radar/1791248400/512/2/1/1/2/1_1.png"
    )
    assert legacy.startswith(b"HTTP/1.1 404 ")
    advertised = await response(
        "tilecache.rainviewer.com", "/v2/radar/f1fa64870793/512/2/1/1/2/1_1.png"
    )
    assert advertised.startswith(b"HTTP/1.1 200 ")
    assert advertised.split(b"\r\n\r\n", 1)[1].startswith(b"\x89PNG\r\n\x1a\n")


def test_detail_fixture_exposes_geographic_feature_absent_from_fallback():
    path = ROOT / "tools/acceptance/overview-weather/provider_fixture.py"
    spec = importlib.util.spec_from_file_location("weather_detail_landmarks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.tile_png(2, 3, z=3, detail=True) != module.tile_png(2, 3, z=3)
    assert module.tile_png(1, 1, z=2, detail=True) == module.tile_png(1, 1, z=2)
