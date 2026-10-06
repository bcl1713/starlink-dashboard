"""Behavior tests use synthetic bulletins; no captured provider inputs in Git."""
import hashlib
import json
from pathlib import Path

import pytest
from shapely.geometry import Point, shape

from acceptance.aviation_weather_proof.model import CaptureManifest, CapturedObject, load_capture, write_manifest

NOW = 1791288000000  # 2026-10-06 12:00 UTC


def feature(**changes):
    props = dict(icaoId="TEST", firId="TEST", seriesId="1", hazard="VA", validTimeFrom="2026-10-06T06:00:00Z", validTimeTo="2026-10-06T13:00:00Z", base=0, top=7000, rawSigmet="SYNTHETIC TEST SFC/FL070")
    props.update(changes)
    return dict(type="Feature", properties=props, geometry=dict(type="Polygon", coordinates=[[[10, 0], [12, 0], [12, 2], [10, 2], [10, 0]]]))


def normalize(tmp_path, features, **collection_fields):
    # Missing normalizer is a behavioral RED assertion, rather than collection error.
    import acceptance.aviation_weather_proof as package
    from importlib.util import find_spec
    assert find_spec(package.__name__ + ".advisory"), "advisory normalizer is not implemented"
    from acceptance.aviation_weather_proof.advisory import normalize_advisories
    root = tmp_path / "capture"
    root.mkdir()
    raw = json.dumps(dict(type="FeatureCollection", features=features, **collection_fields)).encode()
    (root / "source.json").write_bytes(raw)
    write_manifest(CaptureManifest("isigmet", NOW, (CapturedObject("https://aviationweather.gov/api/data/isigmet?format=geojson", None, "source.json", hashlib.sha256(raw).hexdigest(), len(raw)),), ("synthetic",)), root / "capture.json")
    artifact = normalize_advisories(load_capture(root / "capture.json"), tmp_path / "products" / "advisory")
    descriptor = json.loads(artifact.descriptor_path.read_text())
    active = json.loads((artifact.descriptor_path.parent / descriptor["advisories"]["path"]).read_text())
    records = json.loads((artifact.descriptor_path.parent / descriptor["records"]["path"]).read_text())
    return artifact, descriptor, active, records


def test_empty_is_not_worldwide_clear(tmp_path):
    _, d, active, _ = normalize(tmp_path, [])
    assert d["coverage"]["completeness"] == "unverified"
    assert d["coverage"]["worldwide_clear"] is False
    assert active["features"] == []


def test_truncated_feed_is_incomplete(tmp_path):
    _, d, _, _ = normalize(tmp_path, [feature()], truncated=True)
    assert d["coverage"]["completeness"] == "incomplete"
    assert "provider-declared-truncation" in d["coverage"]["reasons"]
    assert d["coverage"]["worldwide_clear"] is False


def test_unknown_vertical_is_not_all_levels(tmp_path):
    _, _, active, _ = normalize(tmp_path, [feature(rawSigmet="SYNTHETIC TEST NO ALTITUDE")])
    vertical = active["features"][0]["properties"]["vertical"]
    assert vertical["status"] == "unknown"
    assert vertical["base"] is None and vertical["top"] is None
    assert vertical["provider_numeric"] == {"base": 0, "top": 7000, "units": "unknown", "reference": "unknown"}


def test_cancelled_or_expired_is_not_active(tmp_path):
    _, _, active, records = normalize(tmp_path, [feature(rawSigmet="SYNTHETIC CNL SIGMET 1"), feature(seriesId="2", validTimeTo="2026-10-06T12:00:00Z"), feature(seriesId="3", validTimeFrom="2026-10-06T12:01:00Z")])
    assert active["features"] == []
    assert [r["properties"]["status"] for r in records["features"]] == ["cancelled", "expired", "future"]


def test_dateline_hole_geometry(tmp_path):
    f = feature()
    f["geometry"]["coordinates"] = [[[170, -10], [-170, -10], [-170, 10], [170, 10], [170, -10]], [[174, -2], [178, -2], [178, 2], [174, 2], [174, -2]], [[179, 4], [-179, 4], [-179, 6], [179, 6], [179, 4]]]
    _, _, active, _ = normalize(tmp_path, [f])
    output = shape(active["features"][0]["geometry"])
    assert output.geom_type == "MultiPolygon"
    assert output.is_valid and output.area == pytest.approx(380)
    assert not output.covers(Point(176, 0))
    assert not output.covers(Point(179.5, 5))
    assert not output.covers(Point(-179.5, 5))
    assert output.covers(Point(172, 0)) and output.covers(Point(-172, 0))
    for polygon in output.geoms:
        for ring in [polygon.exterior, *polygon.interiors]:
            assert all(abs(a[0]-b[0]) <= 180 for a, b in zip(ring.coords, list(ring.coords)[1:]))


def test_raw_explicit_vertical_and_provenance(tmp_path):
    artifact, d, active, _ = normalize(tmp_path, [feature()])
    p = active["features"][0]["properties"]
    assert p["vertical"]["base"] == {"kind": "surface", "value": 0, "units": "surface", "reference": "surface"}
    assert p["vertical"]["top"] == {"kind": "flight-level", "value": 70, "units": "hundreds-ft", "reference": "standard-pressure"}
    assert p["validity"] == {"start_ms": 1791266400000, "end_ms": 1791291600000, "interval": "[start,end)"}
    assert p["issuer"] == "TEST" and p["raw_text"] == "SYNTHETIC TEST SFC/FL070"
    assert artifact.capture_manifest_path.is_file()
    assert "capture_manifest_path" not in d
    for key in ("advisories", "records"):
        payload = artifact.descriptor_path.parent / d[key]["path"]
        assert d[key]["sha256"] == hashlib.sha256(payload.read_bytes()).hexdigest()


def test_invalid_geometry_retains_textual_record(tmp_path):
    f = feature()
    f["geometry"]["coordinates"] = [[[10, 0], [12, 2], [10, 2], [12, 0], [10, 0]]]
    _, d, active, records = normalize(tmp_path, [f])
    assert active["features"] == []
    assert records["features"][0]["geometry"] is None
    assert records["features"][0]["properties"]["location_status"] == "unlocated"
    assert d["counts"]["unlocated"] == 1


def test_cap_declares_incomplete_without_unbounded_output(tmp_path):
    _, d, active, records = normalize(tmp_path, [feature(seriesId=str(n)) for n in range(501)])
    assert d["coverage"]["completeness"] == "incomplete"
    assert d["counts"]["source"] == 501 and d["counts"]["retained"] == 500
    assert len(records["features"]) == len(active["features"]) == 500


def test_changed_source_and_existing_destination_rejected(tmp_path):
    artifact, _, _, _ = normalize(tmp_path, [feature()])
    from acceptance.aviation_weather_proof.advisory import normalize_advisories
    capture = load_capture(artifact.capture_manifest_path)
    with pytest.raises(ValueError, match="exists"):
        normalize_advisories(capture, artifact.descriptor_path.parent)
    (artifact.capture_manifest_path.parent / "source.json").write_text("{}")
    with pytest.raises(ValueError, match="hash/size"):
        normalize_advisories(capture, tmp_path / "products" / "bad")


def test_valid_series_cancellation_suppresses_original(tmp_path):
    _, _, active, records = normalize(tmp_path, [feature(), feature(rawSigmet="SYNTHETIC CNL SIGMET 1")])
    assert active["features"] == []
    assert records["features"][0]["properties"]["status"] == "cancelled-by-series"


def test_different_series_cancellation_does_not_suppress(tmp_path):
    _, _, active, _ = normalize(tmp_path, [feature(), feature(seriesId="2", rawSigmet="SYNTHETIC CNL SIGMET 2")])
    assert len(active["features"]) == 1


def test_revision_preserves_lineage_without_fabricated_order(tmp_path):
    _, _, active, records = normalize(tmp_path, [feature(rawSigmet="SYNTHETIC AMD FL100/FL200")])
    p = records["features"][0]["properties"]
    assert p["revision"]["status"] == "declared"
    assert len(p["revision"]["source_feature_sha256"]) == 64
    assert p["source_index"] == 0
    assert active["features"][0]["id"] == records["features"][0]["id"]


@pytest.mark.parametrize("changes", [{"validTimeFrom": "2026-10-06T06:00:00"}, {"validTimeTo": 1791291600}, {"validTimeTo": "2026-10-06T05:00:00Z"}])
def test_unknown_or_reversed_validity_is_not_active(tmp_path, changes):
    _, _, active, records = normalize(tmp_path, [feature(**changes)])
    assert active["features"] == []
    assert records["features"][0]["properties"]["status"] == "unknown-validity"


def test_generation_quota_prevents_partial_publication(tmp_path, monkeypatch):
    from acceptance.aviation_weather_proof import grid
    monkeypatch.setattr(grid, "MAX_GENERATION_BYTES", 100)
    with pytest.raises(ValueError, match="generation quota"):
        normalize(tmp_path, [feature()])
    assert not (tmp_path / "products" / "advisory").exists()
    assert not list(tmp_path.rglob(".grid-stage-*"))


def test_vertex_cap_preserves_text_and_marks_incomplete(tmp_path, monkeypatch):
    from acceptance.aviation_weather_proof import advisory
    monkeypatch.setattr(advisory, "MAX_VERTICES", 4)
    _, d, active, records = normalize(tmp_path, [feature()])
    assert d["coverage"]["completeness"] == "incomplete"
    assert active["features"] == []
    assert records["features"][0]["properties"]["raw_text"] == "SYNTHETIC TEST SFC/FL070"


@pytest.mark.parametrize("west,east", [(170, 190), (-190, -170)])
def test_provider_unwrapped_dateline_coordinates(tmp_path, west, east):
    # AWC sometimes shifts WI longitudes by360 to keep source rings continuous.
    f = feature()
    f["geometry"]["coordinates"] = [[[west, -10], [east, -10], [east, 10], [west, 10], [west, -10]]]
    _, _, active, records = normalize(tmp_path, [f])
    assert len(active["features"]) == 1
    polygon = shape(active["features"][0]["geometry"])
    assert polygon.is_valid and polygon.geom_type == "MultiPolygon"
    assert polygon.area == pytest.approx(400)
    assert polygon.covers(Point(175, 0)) and polygon.covers(Point(-175, 0))
    assert not polygon.covers(Point(0, 0))
    assert records["features"][0]["properties"]["location_status"] == "located"
