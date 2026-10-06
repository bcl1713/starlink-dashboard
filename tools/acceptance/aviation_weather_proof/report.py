"""Fail-closed diagnostic gates over retained source, CPU and native GPU evidence."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .model import confined, file_hash, load_capture


def evaluate_proofs(evidence: Path) -> dict:
    gates: dict[str, dict] = {}

    def gate(name, check):
        try:
            check()
            gates[name] = {"status": "passed"}
        except (
            AssertionError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            AttributeError,
            OverflowError,
        ) as error:
            gates[name] = {"status": "failed", "reason": str(error) or name}

    def read(name):
        return json.loads((evidence / name).read_text())

    def provenance():
        for source in ("gfs", "isigmet", "goes19-c13"):
            path = evidence / "captures" / source / "capture.json"
            capture = load_capture(path)
            assert capture.source == source
            d = read(f"products/{source}/descriptor.json")
            assert d["capture_manifest_sha256"] == file_hash(
                path
            ), "capture hash mismatch"
            assert {
                (o["url"], o["sha256"], o["byte_size"])
                for o in d.get(
                    "source_objects", d.get("provenance", {}).get("source_objects", [])
                )
            } == {
                (o.url, o.sha256, o.byte_size) for o in capture.objects
            }, "source URL/hash mismatch"
            payloads = list(d.get("components", {}).values()) + [
                d[k] for k in ("mask", "advisories", "records") if k in d
            ]
            for p in payloads:
                f = confined(evidence / "products" / source, p["path"])
                assert (
                    f.stat().st_size == p["byte_size"] and file_hash(f) == p["sha256"]
                ), "payload mismatch"

    def scientific():
        def number(value, low, high):
            assert (
                type(value) in (int, float)
                and math.isfinite(value)
                and low <= value <= high
            ), "nonfinite/out-of-budget scientific measurement"

        def instant(date, hhmm):
            return int(
                datetime.strptime(f"{date}{hhmm:04d}", "%Y%m%d%H%M")
                .replace(tzinfo=timezone.utc)
                .timestamp()
                * 1000
            )

        for source in ("gfs", "goes19-c13", "isigmet"):
            descriptor_path = evidence / "products" / source / "descriptor.json"
            d = read(f"products/{source}/descriptor.json")
            capture = load_capture(evidence / "captures" / source / "capture.json")
            expected = {
                "source": source,
                "capture_manifest_sha256": file_hash(
                    evidence / "captures" / source / "capture.json"
                ),
                "descriptor_sha256": file_hash(descriptor_path),
                "times": {
                    key: d.get(key)
                    for key in (
                        "run_at_ms",
                        "lead_seconds",
                        "valid_at_ms",
                        "valid_from_ms",
                        "valid_to_ms",
                        "scan_start_ms",
                        "scan_end_ms",
                        "diagnostic_replay_at_ms",
                    )
                },
            }
            receipt = read(f"oracles/{source}-source.json")
            metrics = read(f"oracles/{source}-normalize-metrics.json")
            assert (
                receipt["binding"] == metrics["binding"] == expected
            ), "unbound scientific evidence"
            assert metrics["source"] == source and metrics["mode"] == "normalize"
            number(metrics["elapsed_seconds"], 1e-9, 120)
            number(metrics["cpu_seconds"], 1e-9, 120)
            number(metrics["max_rss_bytes"], 1, 1024**3)
            number(metrics["cgroup_memory_peak_bytes"], 1, 1024**3)
            records = receipt["comparisons"]
            if source == "isigmet":
                assert (
                    records["normalized"] is True
                    and records["descriptor"] == d["counts"]
                )
                continue
            assert len(records) >= 10
            assert (
                len({(r["longitude"], r["latitude"]) for r in records}) >= 10
            ), "duplicate source controls"
            hashes = {o.sha256 for o in capture.objects}
            for r in records:
                number(r["longitude"], -180, 180)
                number(r["latitude"], -90, 90)
                assert r["normalized_mask"] == 0
                if source == "gfs":
                    assert set(r["source_values"]) == {"t", "u", "v"}
                    for component in ("t", "u", "v"):
                        assert r["source_hashes"][component] in hashes
                        metadata = r["source_metadata"][component]
                        assert (
                            instant(metadata["dataDate"], metadata["dataTime"])
                            == d["run_at_ms"]
                        )
                        assert (
                            instant(metadata["validityDate"], metadata["validityTime"])
                            == d["valid_at_ms"]
                        )
                        assert metadata["endStep"] * 3600 == d["lead_seconds"]
                        tolerance = d["components"][component]["scale"] / 2
                        number(tolerance, 1e-12, 0.005)
                        assert r["quantization_tolerance"][component] == tolerance
                        assert (
                            r["resampling_tolerance"][component]
                            == r["resampling_error"][component]
                            == 0
                        )
                        error = abs(
                            r["source_values"][component]
                            - r["normalized_values"][component]
                        )
                        number(error, 0, tolerance + 1e-9)
                        assert abs(error - r["absolute_error"][component]) < 1e-12
                else:
                    assert r["source_hash"] in hashes
                    assert (
                        r["scan_start_ms"] == d["scan_start_ms"]
                        and r["scan_end_ms"] == d["scan_end_ms"]
                    )
                    assert (d["time_kind"], d["method_kind"], d["validity_kind"]) == (
                        "observation",
                        "sensor",
                        "instant",
                    )
                    assert (
                        d["valid_at_ms"] == d["scan_end_ms"]
                        and d["valid_from_ms"] is None
                        and d["valid_to_ms"] is None
                    )
                    tolerance = d["components"]["t"]["scale"] / 2
                    number(tolerance, 1e-12, 0.005)
                    assert r["quantization_tolerance"] == tolerance
                    contributors = r["source_contributors"]
                    assert (
                        contributors
                        and abs(sum(p["weight"] for p in contributors) - 1) < 1e-9
                    )
                    for p in contributors:
                        assert p["dqf"] == 0
                        number(p["weight"], 0, 1)
                        number(p["navigation_roundtrip_error_rad"], 0, 1e-10)
                        number(p["view_zenith_degrees"], 0, 75)
                        number(p["value_K"], 0, 1000)
                    regridded = sum(p["weight"] * p["value_K"] for p in contributors)
                    assert abs(regridded - r["regridded_value"]) < 1e-9
                    error = abs(regridded - r["normalized_value"])
                    number(error, 0, tolerance + 1e-7)
                    assert abs(error - r["quantization_error"]) < 1e-12
                    number(r["resampling_local_range_bound"], 0, 1000)
                    number(
                        r["resampling_error"],
                        0,
                        r["resampling_local_range_bound"] + 1e-9,
                    )
                    assert (
                        abs(
                            abs(regridded - r["nearest_source_value"])
                            - r["resampling_error"]
                        )
                        < 1e-9
                    )

    def native():
        j = read("browser/journey.json")
        assert j["native_overview"] and j["status"] == "passed"
        assert len(j["captures"]) >= 12 and all(
            (evidence / "browser" / name).stat().st_size > 10000
            for name in j["captures"]
        )
        for source in ("gfs", "goes19-c13"):
            views = [
                v
                for v in j["views"]
                if v["path"].startswith("model-" if source == "gfs" else "satellite-")
            ]
            assert views, "missing scalar captures"
            for view in views:
                palette = view["palette"]
                declaration = palette["declaration"]
                assert palette["visible"] is True and view["path"] in j["captures"]
                assert declaration == {
                    "units": "K",
                    "minimum": 190,
                    "maximum": 310,
                    "ticks": [190, 250, 310],
                    "opacity": 0.4,
                    "stops": [[0, 0.25, 1], [0.5, 0.25, 0.5], [1, 0.25, 0]],
                    "unavailable": "Unavailable: outside coverage (1), missing (2), quality rejected (3); transparent",
                }
                assert all(
                    part in palette["text"]
                    for part in (
                        "190 K",
                        "250 K",
                        "310 K",
                        "40%",
                        declaration["unavailable"],
                    )
                )
            samples = j["samples"][source]
            references = read(f"oracles/{source}-gpu.json")
            assert len(samples) >= 10 and len(samples) == len(references)
            for sample, reference in zip(samples, references, strict=True):
                assert sample["mask"] == reference["mask"] == 0, "failed mask readback"
                assert sample["quantity"][2] == sample["mask"]
                assert (
                    abs(sample["value"] - reference["values"]["t"]) <= 0.01 + 1e-9
                ), "GPU quantity mismatch"
                assert abs(sample["sampleLatitude"] - reference["latitude"]) < 1e-10
                assert abs(sample["sampleLongitude"] - reference["longitude"]) < 1e-10
                value = reference["values"]["t"]
                t = max(0, min(1, (value - 190) / 120))
                expected = [
                    sample["base"][i] * 0.6 + 255 * c * 0.4
                    for i, c in enumerate((t, 0.25, 1 - t))
                ]
                assert (
                    max(abs(sample["color"][i] - expected[i]) for i in range(3)) <= 3
                ), "palette/opacity mismatch"
        for snapshot in j["metrics"]:
            peak = snapshot["allocation"]["peak"]
            assert (
                0 < peak["gpu"] <= 16 * 1024**2
                and 0 < peak["decoded"] <= 32 * 1024**2
                and 0 < peak["encoded"] <= 16 * 1024**2
            ), "GPU metrics missing/budget"
            assert snapshot["viewport"]["width"] > 0 and snapshot["renderer"]["version"]
        assert j["metrics"], "missing GPU metrics"
        processes = read("browser/process-metrics.json")
        assert processes and any(
            p["rss_bytes"] > 0 and p["cpu_seconds"] >= 0
            for row in processes
            for p in row["processes"]
        ), "missing CPU/RSS metrics"
        assert j["restored"]["allocation"]["current"] == {
            "encoded": 0,
            "decoded": 0,
            "gpu": 0,
        }, "owned allocation remains"
        assert all(
            r["allowed"] for r in read("browser/requests.json")
        ), "browser provider request"

    def controls():
        j = read("browser/journey.json")
        required = (
            "regional_ownership",
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
        assert all(
            j["controls"].get(key) is True for key in required
        ), "synthetic controls missing or failed"
        regional = j["synthetic_regions"]
        assert (
            regional["synthetic"] is True and regional["visible"] is True
        ), "regional labels not rendered"
        assert (
            regional["descriptor_url"]
            == "/api/overview-weather/aviation-proof-assets/synthetic/descriptor.json"
        )
        assert regional["capture"] in j["captures"]
        assert "SYNTHETIC regional interval control" in regional["label"]
        for interval in (
            "A: 1970-01-01T00:00:00.000Z – 1970-01-01T00:00:01.000Z",
            "B: 1970-01-01T00:00:02.000Z – 1970-01-01T00:00:03.000Z",
        ):
            assert (
                interval in regional["label"]
            ), "incomplete rendered regional interval"
        assert (
            "Coverage unverified" in j["advisory_label"]
            or "Coverage incomplete" in j["advisory_label"]
        )
        assert "2026-10-06T12:07:27.898Z" in j["advisory_label"]
        assert (
            "2026-10-06T00:00:20.900Z" in j["satellite_label"]
            and "2026-10-06T00:09:52.800Z" in j["satellite_label"]
        )

    def advisory_presentation():
        j = read("browser/journey.json")
        shown = j["selected_advisory"]
        assert shown["visible"] is True and shown["outlineVertices"] > 0
        selected = shown["selectedAdvisory"]
        features = read("products/isigmet/advisories.geojson")["features"]
        assert selected in features
        p = selected["properties"]
        assert (p["issuer"], p["fir_id"], p["series_id"]) == (
            "PHFO",
            "KZAK",
            "VICTOR 6",
        )
        capture = load_capture(evidence / "captures/isigmet/capture.json")
        source = json.loads(
            confined(
                evidence / "captures/isigmet", capture.objects[0].relative_path
            ).read_text()
        )["features"][p["source_index"]]
        assert (
            source["properties"]["rawSigmet"] == p["raw_text"]
        ), "bulletin lineage differs"
        assert p["source_sha256"] == capture.objects[0].sha256
        utc = (
            lambda n: datetime.fromtimestamp(n / 1000, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        parts = [
            p["issuer"],
            p["fir_id"],
            p["series_id"],
            p["hazard"],
            p["qualifier"],
            f'[{utc(p["validity"]["start_ms"])}, {utc(p["validity"]["end_ms"])})',
            "vertical unknown" if p["vertical"]["status"] == "unknown" else "vertical",
        ]
        assert all(part in j["advisory_label"] for part in parts)
        replay = read("products/isigmet/descriptor.json")["diagnostic_replay_at_ms"]
        assert p["validity"]["start_ms"] <= replay < p["validity"]["end_ms"]
        assert f"Diagnostic replay {utc(replay)}" in j["advisory_label"]
        view = next(
            (v for v in j["views"] if v["path"] == "advisory-victor6.png"), None
        )
        assert view is not None, "missing selected advisory capture"
        assert view["selectedAdvisory"] == selected and view["outlineVertices"] > 0
        assert all(part in view["label"] for part in parts)

    def regional_ownership():
        import struct

        receipt = read("oracles/synthetic-source.json")
        d = read("products/synthetic/descriptor.json")
        assert receipt["synthetic"] is True and receipt[
            "descriptor_sha256"
        ] == file_hash(evidence / "products/synthetic/descriptor.json")
        assert receipt["cases"] == d["synthetic_controls"]
        expected = [
            {"region": r, "value": v, "mask": m}
            for r, v, m in [
                ("B", 270, 0),
                ("A", 250, 0),
                ("A", 250, 0),
                ("B", 270, 0),
                (None, None, 3),
            ]
        ]
        assert receipt["expected"] == expected

        def select(candidates):
            # Independent reference policy; do not call the producer selector.
            viable = sorted(
                (c for c in candidates if c["mask"] == 0),
                key=lambda c: (c["view_angle"], -c["scan_end_ms"], c["region"]),
            )
            return (
                {"region": viable[0]["region"], "value": viable[0]["value"], "mask": 0}
                if viable
                else {
                    "region": None,
                    "value": None,
                    "mask": max(c["mask"] for c in candidates),
                }
            )

        assert (
            select(receipt["stable_id_probe"]["candidates"])
            == receipt["stable_id_probe"]["expected"]
            == {"region": "A", "value": 250, "mask": 0}
        )
        arrays = {}
        for name, p in {
            "t": d["components"]["t"],
            "mask": d["mask"],
            "lineage": d["lineage"],
        }.items():
            path = confined(evidence / "products/synthetic", p["path"])
            assert (
                file_hash(path) == p["sha256"] and path.stat().st_size == p["byte_size"]
            )
            arrays[name] = path.read_bytes()
            assert len(arrays[name]) == 720 * 361 * (
                2 if name == "t" else 1
            ), "regional payload dimensions"
        samples = read("browser/journey.json")["regional_samples"]
        assert len(samples) == len(receipt["cases"]) == 5
        for c, want, sample in zip(receipt["cases"], expected, samples, strict=True):
            assert select(c["candidates"]) == want
            assert [
                (p["scan_start_ms"], p["scan_end_ms"]) for p in c["candidates"]
            ] == [(0, 1000), (2000, 3000)]
            index = int((90 - c["latitude"]) * 2) * 720 + int(
                (c["longitude"] + 180) * 2
            )
            assert arrays["mask"][index] == want["mask"]
            assert arrays["lineage"][index] == {None: 0, "A": 1, "B": 2}[want["region"]]
            assert (
                sample["name"] == c["name"]
                and sample["mask"] == want["mask"]
                and sample["region"] == want["region"]
            )
            if want["value"] is None:
                assert sample["value"] is None
            else:
                raw = struct.unpack_from("<h", arrays["t"], index * 2)[0]
                value = (
                    raw * d["components"]["t"]["scale"] + d["components"]["t"]["offset"]
                )
                assert (
                    abs(value - want["value"]) <= 0.005 + 1e-9
                    and abs(sample["value"] - want["value"]) <= 0.01 + 1e-9
                )
        seam = read("browser/journey.json")["regional_seam"]
        assert seam["latitude"] == 30 and seam["longitude"] == -0.25
        assert (
            -0.5 < seam["sampleLongitude"] < 0 and 29.5 < seam["sampleLatitude"] < 30.5
        )
        assert seam["mask"] == 0 and seam["region"] is None
        assert seam["lineage"] == ["A", "B", "A", "B"]
        row = math.floor((90 - seam["sampleLatitude"]) * 2)
        for y in (row, row + 1):
            for x, want in ((359, 1), (360, 2)):
                assert (
                    arrays["lineage"][y * 720 + x] == want
                    and arrays["mask"][y * 720 + x] == 0
                )
                raw = struct.unpack_from("<h", arrays["t"], (y * 720 + x) * 2)[0]
                assert (
                    abs(
                        raw * d["components"]["t"]["scale"]
                        + d["components"]["t"]["offset"]
                        - ({1: 250, 2: 270}[want])
                    )
                    <= 0.005 + 1e-9
                )
        assert (
            abs(seam["value"] - (250 + (seam["sampleLongitude"] + 0.5) * 40))
            <= 0.01 + 1e-9
        )
        label = read("browser/journey.json")["synthetic_regions"]["label"]
        assert "1970-01-01T00:00:00.000Z – 1970-01-01T00:00:00.000Z" not in label
        assert d.get("scan_start_ms") is None and d.get("scan_end_ms") is None

    def cleanup():
        for name in ("cleanup.json", "browser/browser-cleanup.json"):
            result = read(name)
            assert (
                result["status"] == "passed"
                and result.get("remaining") == []
                and result.get("killed_descendants") == []
                and result.get("killed_containers", []) == []
            ), "absent cleanup or killed descendant"

    gate("real_source_provenance", provenance)
    gate("scientific_source_and_budgets", scientific)
    gate("native_gpu_quantities_masks_palette", native)
    gate("synthetic_controls_and_time_labels", controls)
    gate("advisory_context_and_outline", advisory_presentation)
    gate("synthetic_regional_ownership", regional_ownership)
    gate("owned_runtime_cleanup", cleanup)
    return {
        "status": (
            "passed"
            if all(g["status"] == "passed" for g in gates.values())
            else "failed"
        ),
        "diagnostic_only": True,
        "gates": gates,
        "unproven": [
            "conditional WIFS access",
            "flight-level interpolation",
            "worldwide satellite seams",
            "worldwide advisory completeness",
        ],
    }
