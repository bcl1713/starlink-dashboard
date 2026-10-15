"""Independent ISA tables and physical samples prove genuine FL derivation."""

import json
import math
from dataclasses import replace

import numpy as np
import pytest

from app.models.aviation_grid import GfsSelection
from tests.fixtures.gfs_fields import RUN, grib_bundle

# Computed independently with 50-digit Decimal arithmetic, not production code.
ISA = [
    (50, 84307.26454060),
    (100, 69681.64162360),
    (180, 50599.82076785),
    (240, 39270.97804732),
    (300, 30089.56253744),
    (340, 24998.99078423),
    (390, 19677.29330547),
    (450, 14747.66217617),
]


def selection(fl=340):
    return GfsSelection(vertical={"kind": "flight-level", "flight_level": fl})


def fields(root):
    from app.services.aviation_weather.gfs.decode import decode_bundle

    low = grib_bundle(root / "low", pressure=20000)
    high = grib_bundle(root / "high", pressure=30000)
    bundle = replace(
        low,
        ranges=low.ranges[:3] + high.ranges[:3] + low.ranges[3:],
        paths=low.paths[:3] + high.paths[:3] + low.paths[3:],
        hashes=low.hashes[:3] + high.hashes[:3] + low.hashes[3:],
    )
    result = decode_bundle(bundle)
    base = np.arange(12, dtype=float).reshape(3, 4)
    for name, offset, change in [("u", -5, 40), ("v", 3, -30), ("t", 250, 20)]:
        result.components[(name, 20000)][0][:] = base + offset
        result.components[(name, 30000)][0][:] = base + offset + change
    return result


@pytest.mark.parametrize("fl,expected", ISA)
def test_two_segment_isa_matches_independent_pressure_table(fl, expected):
    from app.services.aviation_weather.gfs.vertical import flight_level_pressure

    assert flight_level_pressure(fl) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("fl", [0, 51, 500, True])
def test_only_approved_flight_levels_are_admitted(fl):
    with pytest.raises(ValueError):
        selection(fl)


def test_nearest_actual_brackets_and_legacy_pressure_migration():
    from app.services.aviation_weather.gfs.vertical import source_pressures

    pressures = (
        12500,
        15000,
        17500,
        20000,
        22500,
        25000,
        30000,
        35000,
        40000,
        50000,
        55000,
        65000,
        70000,
        85000,
    )
    expected = [
        (70000, 85000),
        (65000, 70000),
        (50000, 55000),
        (35000, 40000),
        (30000, 35000),
        (22500, 25000),
        (17500, 20000),
        (12500, 15000),
    ]
    for (fl, _), brackets in zip(ISA, expected, strict=True):
        assert source_pressures(selection(fl), pressures) == brackets
    legacy = GfsSelection(pressure_pa=50000, horizon_hours=6)
    assert legacy.vertical.kind == "pressure"
    assert legacy.model_dump() == {
        "vertical": {"kind": "pressure", "pressure_pa": 50000},
        "horizon_hours": 6,
    }
    assert source_pressures(legacy, pressures) == (50000,)
    for available in [(20000,), (30000,), ()]:
        with pytest.raises(ValueError):
            source_pressures(selection(), available)
    with pytest.raises(ValueError):
        source_pressures(legacy, (30000, 70000))


def test_log_pressure_interpolation_and_ten_quantized_geographic_samples(tmp_path):
    from app.services.aviation_weather.gfs.grid import normalize_grid
    from app.services.aviation_weather.gfs.vertical import interpolate_vertical

    original = fields(tmp_path / "source")
    target = 24998.99078423
    weight = math.log(target / 20000) / math.log(30000 / 20000)
    derived = interpolate_vertical(original, target)
    assert derived.components[("u", target)][0][1, 1] == pytest.approx(
        40 * weight, abs=1e-6
    )
    result = normalize_grid(
        original, selection(), tmp_path / "candidate", clock=lambda: RUN / 1000
    )
    vertical = result.descriptor.vertical
    assert vertical.kind == "flight-level" and vertical.flight_level == 340
    assert vertical.reference == "pressure-altitude-1013.25hpa"
    assert vertical.derivation == "isa-log-pressure-v1"
    assert vertical.source_pressures_pa == [20000, 30000]
    arrays = {
        name: np.fromfile(result.directory / f"{name}.bin", dtype="<i2").reshape(
            361, 720
        )
        * 0.01
        + (273.15 if name == "t" else 0)
        for name in ("u", "v", "t")
    }
    # Exact source nodes, seam, poles and a fractional spatial sample.
    samples = [
        (0, 360, 8),
        (0, 0, 10),
        (0, 180, 11),
        (180, 360, 4),
        (180, 540, 5),
        (180, 0, 6),
        (360, 360, 0),
        (360, 0, 2),
        (360, 180, 3),
        (90, 450, 6.5),
    ]
    for row, col, base in samples:
        for name, offset, change in [("u", -5, 40), ("v", 3, -30), ("t", 250, 20)]:
            assert (
                abs(arrays[name][row, col] - (base + offset + change * weight)) <= 0.01
            )
    lineage = json.loads((result.directory / "lineage/source.json").read_bytes())
    assert sorted(
        {r["pressure_pa"] for r in lineage["ranges"] if r["pressure_pa"]}
    ) == [20000, 30000]


@pytest.mark.parametrize("failure", ["missing", "terrain", "surface"])
def test_vertical_contributors_remain_unknown_before_spatial_interpolation(
    tmp_path, failure
):
    from app.services.aviation_weather.gfs.grid import normalize_grid

    original = fields(tmp_path / "source")
    if failure == "missing":
        original.components[("v", 30000)][1][1, 0] = False
    elif failure == "terrain":
        # Target pressure is atmospheric, but its lower bracket is underground.
        original.components[("sp", None)][0][1, 0] = 27000
    else:
        original.components[("sp", None)][1][1, 0] = False
    result = normalize_grid(
        original, selection(), tmp_path / "candidate", clock=lambda: RUN / 1000
    )
    mask = np.fromfile(result.directory / "mask.bin", dtype="u1").reshape(361, 720)
    assert mask[180, 360] == (1 if failure == "terrain" else 2)
    assert mask[181, 361] == (1 if failure == "terrain" else 2)
    assert mask[180, 0] == 0


@pytest.mark.parametrize("change", ["run", "lead", "shape", "missing-bracket"])
def test_vertical_interpolation_rejects_incoherent_fields(tmp_path, change):
    from app.services.aviation_weather.gfs.vertical import interpolate_vertical

    original = fields(tmp_path / "source")
    if change == "run":
        original = replace(original, run_at_ms=RUN + 1)
    elif change == "lead":
        original = replace(original, lead_seconds=0)
    elif change == "shape":
        original.components[("u", 30000)] = (
            np.zeros((2, 4)),
            np.ones((2, 4), dtype=bool),
        )
    else:
        del original.components[("t", 30000)]
    with pytest.raises(ValueError):
        interpolate_vertical(original, 24998.99078423)


def test_publication_preserves_real_brackets_and_native_compatibility(tmp_path):
    from app.services.aviation_weather.gfs.bridge import _envelope, unavailable_products
    from app.services.aviation_weather.gfs.grid import normalize_grid
    from tests.unit.test_gfs_store import store

    products, settings, _enabled = store(tmp_path)
    enabled = settings.update({"gfs_selection": selection().model_dump()})
    result = normalize_grid(
        fields(tmp_path / "source"),
        selection(),
        tmp_path / "candidate",
        clock=lambda: RUN / 1000,
    )
    products.publish(result, enabled.revision)
    current = products.read_current(selection(), RUN)
    assert len(current) == 2
    body = (
        products.root / "products" / current[0].instance_id / "grid.json"
    ).read_bytes()
    model = _envelope("winds", enabled, RUN, current[0], body)
    assert model.vertical.source_pressures_pa == [20000, 30000]
    assert "log-pressure" in model.provenance
    assert all(
        p.vertical.kind == "not-applicable" for p in unavailable_products(enabled, RUN)
    )
    assert products.read_current(GfsSelection(pressure_pa=25000), RUN) == ()


def test_foundation_pointer_selection_migrates_without_changing_its_product(tmp_path):
    from tests.unit.test_gfs_grid import candidate
    from tests.unit.test_gfs_store import store

    products, _, enabled = store(tmp_path)
    products.publish(candidate(tmp_path / "work"), enabled.revision)
    original = products.read_current(GfsSelection(), RUN)
    path = products.root / "current.json"
    pointer = json.loads(path.read_bytes())
    pointer["selection"] = {"pressure_pa": 50000, "horizon_hours": 0}
    path.write_text(json.dumps(pointer))
    assert products.read_current(GfsSelection(), RUN) == original


async def test_flight_level_acquisition_downloads_only_seven_needed_ranges(tmp_path):
    import httpx

    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    key = "gfs.20261006/00/atmos/gfs.t00z.pgrb2.0p25.f000"
    records = [
        (name, f"{p} mb")
        for p in (150, 225, 250, 500)
        for name in ("TMP", "UGRD", "VGRD")
    ] + [("PRES", "surface")]
    index = "".join(
        f"{i+1}:{i*8}:d=2026100600:{name}:{level}:anl:\n"
        for i, (name, level) in enumerate(records)
    ).encode()
    received = []

    def exchange(request):
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"etag": '"fixed"', "content-length": "104"},
                stream=httpx.ByteStream(b""),
            )
        if request.url.path == "/":
            prefix = request.url.params["prefix"]
            item = ""
            if prefix == "gfs.20261006/":
                item = (
                    "<CommonPrefixes><Prefix>gfs.20261006/00/</Prefix></CommonPrefixes>"
                )
            elif prefix.startswith("gfs.20261006/00/atmos/"):
                item = f"<Contents><Key>{key}</Key></Contents><Contents><Key>{key}.idx</Key></Contents>"
            return httpx.Response(
                200,
                stream=httpx.ByteStream(
                    f"<ListBucketResult>{item}<IsTruncated>false</IsTruncated></ListBucketResult>".encode()
                ),
            )
        if request.url.path.endswith(".idx"):
            return httpx.Response(200, stream=httpx.ByteStream(index))
        bounds = request.headers["range"].removeprefix("bytes=")
        received.append(bounds)
        assert request.headers["if-match"] == '"fixed"'
        return httpx.Response(
            206,
            headers={"etag": '"fixed"', "content-range": f"bytes {bounds}/104"},
            stream=httpx.ByteStream(b"abcdefgh"),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(exchange)) as client:
        with GfsQuota(tmp_path / "quota", clock=lambda: RUN / 1000) as quota:
            transport = GfsTransport(quota, client=client, clock=lambda: RUN / 1000)
            bundle = await transport.acquire(selection(), tmp_path / "stage")
    assert len(bundle.paths) == 7
    assert {ref.pressure_pa for ref in bundle.ranges} == {22500, 25000, None}
    assert received == [f"{i*8}-{i*8+7}" for i in (3, 4, 5, 6, 7, 8, 12)]
