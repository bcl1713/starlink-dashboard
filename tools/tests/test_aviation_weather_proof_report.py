"""Mutation tests: each omitted receipt independently closes its report gate."""

import hashlib
import json
from pathlib import Path

import pytest
from acceptance.aviation_weather_proof.report import evaluate_proofs


def write(root, name, data):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def complete(tmp_path: Path) -> Path:
    digest = hashlib.sha256(b"x").hexdigest()
    for source in ("gfs", "isigmet", "goes19-c13"):
        obj = {
            "url": "https://aviationweather.gov/test-unit-only",
            "byte_range": None,
            "relative_path": "source.bin",
            "sha256": digest,
            "byte_size": 1,
        }
        receipt = write(
            tmp_path,
            f"captures/{source}/capture.json",
            {
                "source": source,
                "captured_at_ms": 1,
                "objects": [obj],
                "attribution": ["UNIT TEST SYNTHETIC"],
            },
        )
        (receipt.parent / "source.bin").write_bytes(b"x")
        write(
            tmp_path,
            f"products/{source}/descriptor.json",
            {
                "capture_manifest_sha256": hashlib.sha256(
                    receipt.read_bytes()
                ).hexdigest(),
                "source_objects": [obj],
            },
        )
    sample = {
        "mask": 0,
        "quantity": [0, 0, 0, 255],
        "value": 250,
        "sampleLatitude": 0,
        "sampleLongitude": 0,
        "quantizationStep": 0.01,
        "base": [0, 0, 0],
        "color": [51, 25.5, 51],
    }
    j = {
        "native_overview": True,
        "status": "passed",
        "captures": [f"{i}.png" for i in range(12)],
        "samples": {s: [sample] * 10 for s in ("gfs", "goes19-c13")},
        "metrics": [
            {
                "allocation": {"peak": {"gpu": 8, "decoded": 16, "encoded": 1}},
                "viewport": {"width": 1},
                "renderer": {"version": "TEST"},
            }
        ],
        "restored": {"allocation": {"current": {"encoded": 0, "decoded": 0, "gpu": 0}}},
        "controls": {
            name: True
            for name in (
                "seam",
                "poles",
                "invalid",
                "failed_install_ownership",
                "holes",
                "expiry",
                "cancelled",
                "directional",
                "asynchronous",
                "advisory_dateline",
                "asynchronous_ownership",
                "camera_restored",
            )
        },
        "advisory_label": "Coverage unverified 2026-10-06T12:07:27.898Z",
        "satellite_label": "2026-10-06T00:00:20.900Z 2026-10-06T00:09:52.800Z",
    }
    j["synthetic_regions"] = {
        "synthetic": True,
        "visible": True,
        "descriptor_url": "/api/overview-weather/aviation-proof-assets/synthetic/descriptor.json",
        "capture": "0.png",
        "label": "SYNTHETIC regional interval control A: 1970-01-01T00:00:00.000Z – 1970-01-01T00:00:01.000Z B: 1970-01-01T00:00:02.000Z – 1970-01-01T00:00:03.000Z",
    }
    write(tmp_path, "browser/journey.json", j)
    for name in j["captures"]:
        (tmp_path / "browser" / name).write_bytes(b"x" * 10001)
    for source in ("gfs", "goes19-c13"):
        write(
            tmp_path,
            f"oracles/{source}-gpu.json",
            [{"mask": 0, "values": {"t": 250}, "latitude": 0, "longitude": 0}] * 10,
        )
    write(tmp_path, "browser/requests.json", [{"allowed": True}])
    write(
        tmp_path,
        "browser/process-metrics.json",
        [{"processes": [{"rss_bytes": 1, "cpu_seconds": 0}]}],
    )
    for name in ("cleanup.json", "browser/browser-cleanup.json"):
        write(
            tmp_path,
            name,
            {"status": "passed", "remaining": [], "killed_descendants": []},
        )
    enrich_complete(tmp_path)
    return tmp_path


def test_structurally_complete_unit_fixture_passes(complete):
    assert evaluate_proofs(complete)["status"] == "passed"


@pytest.mark.parametrize(
    "fault",
    [
        "missing_capture",
        "hash_mismatch",
        "url_mismatch",
        "gpu_metrics",
        "mask",
        "cleanup",
        "killed_descendant",
        "cpu_metrics",
        "missing_control",
    ],
)
def test_incomplete_proof_never_passes(complete: Path, fault: str):
    if fault == "missing_capture":
        (complete / "captures/gfs/source.bin").unlink()
    elif fault in ("hash_mismatch", "url_mismatch"):
        path = complete / "products/gfs/descriptor.json"
        d = json.loads(path.read_text())
        d["source_objects"][0][
            "sha256" if fault == "hash_mismatch" else "url"
        ] = "mismatch"
        path.write_text(json.dumps(d))
    elif fault in ("gpu_metrics", "mask"):
        path = complete / "browser/journey.json"
        j = json.loads(path.read_text())
        if fault == "gpu_metrics":
            j["metrics"] = []
        else:
            j["samples"]["gfs"][0]["mask"] = 3
        path.write_text(json.dumps(j))
    elif fault == "cpu_metrics":
        (complete / "browser/process-metrics.json").unlink()
    elif fault == "missing_control":
        path = complete / "browser/journey.json"
        j = json.loads(path.read_text())
        del j["controls"]["holes"]
        path.write_text(json.dumps(j))
    elif fault == "cleanup":
        (complete / "cleanup.json").unlink()
    else:
        write(
            complete,
            "browser/browser-cleanup.json",
            {"status": "passed", "remaining": [], "killed_descendants": [12345]},
        )
    assert evaluate_proofs(complete)["status"] == "failed"


def test_empty_evidence_is_failed(tmp_path: Path):
    assert evaluate_proofs(tmp_path)["status"] == "failed"


@pytest.mark.parametrize("fault", ["missing", "hidden", "incomplete_interval"])
def test_unrendered_regional_intervals_cannot_pass(complete, fault):
    path = complete / "browser/journey.json"
    j = json.loads(path.read_text())
    if fault == "missing":
        j.pop("synthetic_regions", None)
    elif fault == "hidden":
        j["synthetic_regions"]["visible"] = False
    else:
        j["synthetic_regions"]["label"] = j["synthetic_regions"]["label"].replace(
            "1970-01-01T00:00:03.000Z", ""
        )
    path.write_text(json.dumps(j))
    assert evaluate_proofs(complete)["status"] == "failed"


def test_forced_container_cleanup_never_passes(complete):
    write(
        complete,
        "cleanup.json",
        {
            "status": "passed",
            "remaining": [],
            "killed_descendants": [],
            "killed_containers": ["owned-worker"],
        },
    )
    assert evaluate_proofs(complete)["status"] == "failed"


@pytest.mark.parametrize("source", ["gfs", "goes19-c13", "isigmet"])
@pytest.mark.parametrize("kind", ["source", "normalize-metrics"])
def test_scientific_receipts_are_mandatory(complete, source, kind):
    (complete / f"oracles/{source}-{kind}.json").unlink(missing_ok=True)
    assert evaluate_proofs(complete)["status"] == "failed"


def enrich_complete(root):
    """Explicit unit-only receipts; no scientific or browser execution is claimed."""
    import struct

    hash_path = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    times = (
        "run_at_ms",
        "lead_seconds",
        "valid_at_ms",
        "valid_from_ms",
        "valid_to_ms",
        "scan_start_ms",
        "scan_end_ms",
        "diagnostic_replay_at_ms",
    )
    feature = {
        "type": "Feature",
        "id": "victor",
        "geometry": None,
        "properties": {
            "issuer": "PHFO",
            "fir_id": "KZAK",
            "series_id": "VICTOR 6",
            "hazard": "TC",
            "qualifier": "KOGUMA",
            "validity": {"start_ms": 1791271800000, "end_ms": 1791293400000},
            "vertical": {"status": "unknown"},
            "raw_text": "UNIT BULLETIN",
            "source_index": 0,
        },
    }
    source_path = write(
        root,
        "captures/isigmet/source.bin",
        {"features": [{"properties": {"rawSigmet": "UNIT BULLETIN"}}]},
    )
    capture_path = root / "captures/isigmet/capture.json"
    capture = json.loads(capture_path.read_text())
    capture["objects"][0].update(
        sha256=hash_path(source_path), byte_size=source_path.stat().st_size
    )
    write(root, "captures/isigmet/capture.json", capture)
    feature["properties"]["source_sha256"] = hash_path(source_path)
    write(root, "products/isigmet/advisories.geojson", {"features": [feature]})
    for source in ("gfs", "goes19-c13", "isigmet"):
        dp = root / f"products/{source}/descriptor.json"
        d = json.loads(dp.read_text())
        cp = root / f"captures/{source}/capture.json"
        cap = json.loads(cp.read_text())
        d.update(capture_manifest_sha256=hash_path(cp), source_objects=cap["objects"])
        d["components"] = {}
        for k in ("t", "u", "v"):
            payload = root / f"products/{source}/{k}.bin"
            payload.write_bytes(b"x")
            d["components"][k] = dict(
                scale=0.01, path=payload.name, byte_size=1, sha256=hash_path(payload)
            )
        digest = cap["objects"][0]["sha256"]
        if source == "gfs":
            d.update(
                run_at_ms=1791244800000, lead_seconds=21600, valid_at_ms=1791266400000
            )
            records = [
                dict(
                    longitude=i,
                    latitude=0,
                    normalized_mask=0,
                    source_values={k: 250 for k in ("t", "u", "v")},
                    normalized_values={k: 250 for k in ("t", "u", "v")},
                    source_hashes={k: digest for k in ("t", "u", "v")},
                    source_metadata={
                        k: dict(
                            dataDate=20261006,
                            dataTime=0,
                            validityDate=20261006,
                            validityTime=600,
                            endStep=6,
                        )
                        for k in ("t", "u", "v")
                    },
                    quantization_tolerance={k: 0.005 for k in ("t", "u", "v")},
                    resampling_tolerance={k: 0 for k in ("t", "u", "v")},
                    resampling_error={k: 0 for k in ("t", "u", "v")},
                    absolute_error={k: 0 for k in ("t", "u", "v")},
                )
                for i in range(10)
            ]
        elif source == "goes19-c13":
            d.update(
                scan_start_ms=1791244820900,
                scan_end_ms=1791245392800,
                valid_at_ms=1791245392800,
                valid_from_ms=None,
                valid_to_ms=None,
                time_kind="observation",
                method_kind="sensor",
                validity_kind="instant",
            )
            records = [
                dict(
                    longitude=i,
                    latitude=0,
                    normalized_mask=0,
                    source_hash=digest,
                    scan_start_ms=d["scan_start_ms"],
                    scan_end_ms=d["scan_end_ms"],
                    quantization_tolerance=0.005,
                    source_contributors=[
                        dict(
                            weight=1,
                            dqf=0,
                            navigation_roundtrip_error_rad=0,
                            view_zenith_degrees=0,
                            value_K=250,
                        )
                    ],
                    regridded_value=250,
                    normalized_value=250,
                    quantization_error=0,
                    resampling_local_range_bound=0,
                    resampling_error=0,
                    nearest_source_value=250,
                )
                for i in range(10)
            ]
        else:
            d["components"] = {}
            d.update(
                counts={"source": 1, "retained": 1},
                diagnostic_replay_at_ms=1791288447898,
            )
            records = {"normalized": True, "descriptor": d["counts"]}
        write(root, f"products/{source}/descriptor.json", d)
        binding = dict(
            source=source,
            capture_manifest_sha256=hash_path(cp),
            descriptor_sha256=hash_path(dp),
            times={k: d.get(k) for k in times},
        )
        write(
            root,
            f"oracles/{source}-source.json",
            {"binding": binding, "comparisons": records},
        )
        write(
            root,
            f"oracles/{source}-normalize-metrics.json",
            dict(
                binding=binding,
                source=source,
                mode="normalize",
                elapsed_seconds=1,
                cpu_seconds=0.5,
                max_rss_bytes=1000,
                cgroup_memory_peak_bytes=2000,
            ),
        )
    # Five literal controls cover fallback, view angle, recency, and invalidity.
    cases = []
    values = bytearray(struct.pack("<h", -2315) * (361 * 720))
    mask = bytearray(361 * 720)
    lineage = bytearray([1]) * (361 * 720)
    expected = [
        dict(region=r, value=v, mask=m)
        for r, v, m in [
            ("B", 270, 0),
            ("A", 250, 0),
            ("A", 250, 0),
            ("B", 270, 0),
            (None, None, 3),
        ]
    ]
    for i, (name, am, bm, av, bv) in enumerate(
        [
            ("valid-over-missing", 2, 0, 10, 30),
            ("valid-over-rejected", 0, 3, 30, 10),
            ("lower-view-angle", 0, 0, 10, 30),
            ("newer-scan", 0, 0, 10, 10),
            ("all-invalid", 2, 3, 10, 10),
        ]
    ):
        lon = -120 + i * 20
        index = 140 * 720 + (lon + 180) * 2
        want = expected[i]
        cases.append(
            dict(
                name=name,
                longitude=lon,
                latitude=20,
                candidates=[
                    dict(
                        region="A",
                        mask=am,
                        value=250,
                        view_angle=av,
                        scan_start_ms=0,
                        scan_end_ms=1000,
                    ),
                    dict(
                        region="B",
                        mask=bm,
                        value=270,
                        view_angle=bv,
                        scan_start_ms=2000,
                        scan_end_ms=3000,
                    ),
                ],
            )
        )
        struct.pack_into(
            "<h", values, index * 2, round(((want["value"] or 273.15) - 273.15) / 0.01)
        )
        mask[index] = want["mask"]
        lineage[index] = {None: 0, "A": 1, "B": 2}[want["region"]]
    for row in (119, 120, 121):
        for col, owner, value in ((359, 1, 250), (360, 2, 270)):
            index = row * 720 + col
            lineage[index] = owner
            mask[index] = 0
            struct.pack_into("<h", values, index * 2, round((value - 273.15) / 0.01))
    d = {
        "synthetic_controls": cases,
        "components": {},
        "scan_start_ms": None,
        "scan_end_ms": None,
    }
    for name, data in [("t", values), ("mask", mask), ("lineage", lineage)]:
        path = root / f"products/synthetic/{name}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        item = dict(path=path.name, byte_size=len(data), sha256=hash_path(path))
        if name == "t":
            d["components"]["t"] = {**item, "scale": 0.01, "offset": 273.15}
        else:
            d[name] = item
    dp = write(root, "products/synthetic/descriptor.json", d)
    write(
        root,
        "oracles/synthetic-source.json",
        dict(
            synthetic=True,
            descriptor_sha256=hash_path(dp),
            cases=cases,
            expected=expected,
            stable_id_probe={
                "candidates": [
                    dict(
                        region="B", mask=0, value=270, view_angle=10, scan_end_ms=1000
                    ),
                    dict(
                        region="A", mask=0, value=250, view_angle=10, scan_end_ms=1000
                    ),
                ],
                "expected": dict(region="A", value=250, mask=0),
            },
        ),
    )
    j = json.loads((root / "browser/journey.json").read_text())
    j["controls"]["regional_ownership"] = True
    j["regional_seam"] = dict(
        latitude=30,
        longitude=-0.25,
        sampleLatitude=30,
        sampleLongitude=-0.25,
        mask=0,
        region=None,
        lineage=["A", "B", "A", "B"],
        value=260,
    )
    j["regional_samples"] = [
        dict(name=c["name"], **want) for c, want in zip(cases, expected)
    ]
    j["advisory_label"] = (
        "PHFO KZAK VICTOR 6 TC KOGUMA [2026-10-06T07:30:00.000Z, 2026-10-06T13:30:00.000Z) vertical unknown Coverage unverified Diagnostic replay 2026-10-06T12:07:27.898Z"
    )
    j["selected_advisory"] = dict(
        visible=True, outlineVertices=8, selectedAdvisory=feature
    )
    palette = dict(
        units="K",
        minimum=190,
        maximum=310,
        ticks=[190, 250, 310],
        opacity=0.4,
        stops=[[0, 0.25, 1], [0.5, 0.25, 0.5], [1, 0.25, 0]],
        unavailable="Unavailable: outside coverage (1), missing (2), quality rejected (3); transparent",
    )
    j["views"] = [
        dict(
            path=name,
            palette=dict(
                visible=True,
                text="190 K 250 K 310 K 40% " + palette["unavailable"],
                declaration=palette,
            ),
        )
        for name in ("model-world.png", "satellite-americas.png")
    ]
    j["views"].append(
        dict(
            path="advisory-victor6.png",
            label=j["advisory_label"],
            selectedAdvisory=feature,
            outlineVertices=8,
        )
    )
    for view in j["views"]:
        j["captures"].append(view["path"])
        (root / "browser" / view["path"]).write_bytes(b"x" * 10001)
    write(root, "browser/journey.json", j)


@pytest.mark.parametrize("source", ["gfs", "goes19-c13", "isigmet"])
@pytest.mark.parametrize(
    "fault",
    [
        "source_binding",
        "metric_binding",
        "elapsed_nan",
        "elapsed_over",
        "cpu_missing",
        "cpu_inf",
        "rss_over",
        "cgroup_zero",
    ],
)
def test_corrupt_scientific_binding_and_budgets_fail(complete, source, fault):
    kind = "source" if fault == "source_binding" else "normalize-metrics"
    path = complete / f"oracles/{source}-{kind}.json"
    r = json.loads(path.read_text())
    if fault.endswith("binding"):
        r["binding"]["descriptor_sha256"] = "wrong"
    elif fault == "cpu_missing":
        r.pop("cpu_seconds")
    else:
        key, value = {
            "elapsed_nan": ("elapsed_seconds", float("nan")),
            "elapsed_over": ("elapsed_seconds", 121),
            "cpu_inf": ("cpu_seconds", float("inf")),
            "rss_over": ("max_rss_bytes", 1024**3 + 1),
            "cgroup_zero": ("cgroup_memory_peak_bytes", 0),
        }[fault]
        r[key] = value
    path.write_text(json.dumps(r))
    assert (
        evaluate_proofs(complete)["gates"]["scientific_source_and_budgets"]["status"]
        == "failed"
    )


@pytest.mark.parametrize("source", ["gfs", "goes19-c13"])
@pytest.mark.parametrize(
    "fault", ["count", "hash", "time", "tolerance", "value", "mask"]
)
def test_corrupt_source_comparisons_fail(complete, source, fault):
    path = complete / f"oracles/{source}-source.json"
    r = json.loads(path.read_text())
    c = r["comparisons"][0]
    if fault == "count":
        r["comparisons"] = r["comparisons"][:9]
    elif fault == "mask":
        c["normalized_mask"] = 3
    elif source == "gfs":
        if fault == "hash":
            c["source_hashes"]["t"] = "wrong"
        if fault == "time":
            c["source_metadata"]["t"]["validityTime"] = 700
        if fault == "tolerance":
            c["quantization_tolerance"]["t"] = 0.006
        if fault == "value":
            c["normalized_values"]["t"] = 251
    else:
        if fault == "hash":
            c["source_hash"] = "wrong"
        if fault == "time":
            c["scan_start_ms"] += 1
        if fault == "tolerance":
            c["quantization_tolerance"] = 0.006
        if fault == "value":
            c["normalized_value"] = 251
    path.write_text(json.dumps(r))
    assert (
        evaluate_proofs(complete)["gates"]["scientific_source_and_budgets"]["status"]
        == "failed"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "legend_hidden",
        "legend_missing",
        "legend_changed",
        "bulletin",
        "outline",
        "owner",
        "regional_value",
        "regional_mask",
        "regional_missing",
    ],
)
def test_visible_and_regional_evidence_is_required(complete, fault):
    path = complete / "browser/journey.json"
    j = json.loads(path.read_text())
    if fault == "legend_hidden":
        j["views"][0]["palette"]["visible"] = False
    elif fault == "legend_missing":
        j["views"][0].pop("palette")
    elif fault == "legend_changed":
        j["views"][0]["palette"]["declaration"]["maximum"] = 320
    elif fault == "bulletin":
        j["advisory_label"] = "anonymous polygon"
    elif fault == "outline":
        j["selected_advisory"]["outlineVertices"] = 0
    elif fault == "owner":
        j["regional_samples"][0]["region"] = "A"
    elif fault == "regional_value":
        j["regional_samples"][0]["value"] = 250
    elif fault == "regional_mask":
        j["regional_samples"][4]["mask"] = 0
    else:
        (complete / "oracles/synthetic-source.json").unlink()
    path.write_text(json.dumps(j))
    assert evaluate_proofs(complete)["status"] == "failed"


@pytest.mark.parametrize("kind", ["source", "normalize-metrics"])
@pytest.mark.parametrize("source", ["gfs", "goes19-c13", "isigmet"])
def test_malformed_scientific_json_closes_gate(complete, kind, source):
    (complete / f"oracles/{source}-{kind}.json").write_text("{")
    assert (
        evaluate_proofs(complete)["gates"]["scientific_source_and_budgets"]["status"]
        == "failed"
    )


@pytest.mark.parametrize(
    "fault",
    ["seam_lineage", "seam_value", "seam_mask", "lineage_hash", "expected_owner"],
)
def test_regional_seam_and_retained_expectations_fail_closed(complete, fault):
    if fault == "lineage_hash":
        (complete / "products/synthetic/lineage.bin").write_bytes(b"wrong")
    elif fault == "expected_owner":
        path = complete / "oracles/synthetic-source.json"
        r = json.loads(path.read_text())
        r["expected"][0]["region"] = "A"
        path.write_text(json.dumps(r))
    else:
        path = complete / "browser/journey.json"
        j = json.loads(path.read_text())
        seam = j["regional_seam"]
        if fault == "seam_lineage":
            seam["lineage"] = ["A"] * 4
        if fault == "seam_value":
            seam["value"] = 250
        if fault == "seam_mask":
            seam["mask"] = 1
        path.write_text(json.dumps(j))
    assert (
        evaluate_proofs(complete)["gates"]["synthetic_regional_ownership"]["status"]
        == "failed"
    )


def test_missing_selected_advisory_view_fails_without_raising(complete):
    path = complete / "browser/journey.json"
    j = json.loads(path.read_text())
    j["views"] = [v for v in j["views"] if v["path"] != "advisory-victor6.png"]
    path.write_text(json.dumps(j))
    assert (
        evaluate_proofs(complete)["gates"]["advisory_context_and_outline"]["status"]
        == "failed"
    )
