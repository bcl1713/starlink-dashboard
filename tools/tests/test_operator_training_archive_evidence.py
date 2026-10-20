"""Private archive proof derives facts from separate normal backend reads."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "operator_training_archive_evidence",
    ROOT / "tools/training/operator-mission/archive_evidence.py",
)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def snapshot():
    one = {
        "record_id": "a",
        "version": 1,
        "journal_seq": 1,
        "mission_id": "m",
        "command_id": "one",
    }
    two = dict(one, version=2, journal_seq=2, command_id="two")
    return {
        "health": {
            "ready": True,
            "store_id": "store",
            "api_epoch": "epoch",
            "source_mode": "simulation",
            "simulation_run_id": "private",
        },
        "H": 2,
        "records": [two],
        "history": [one, two],
        "missions": [{"id": "m"}],
    }


def test_archive_boundary_uses_actual_history_at_capture_h_not_later_current_state():
    source = snapshot()
    journal = {
        "store_id": "store",
        "source_mode": "simulation",
        "simulation_run_id": "private",
        "mission_id": "m",
        "high_water": 1,
        "current_records": source["history"][:1],
    }
    boundary = evidence.archive_boundary(source, journal)
    assert boundary["records"] == source["history"][:1]
    assert boundary["history"] == source["history"][:1]
    assert boundary["H"] == 1
    for changed in [
        dict(journal, store_id="foreign"),
        dict(journal, high_water=3),
        dict(
            journal, current_records=[dict(source["history"][0], command_id="invented")]
        ),
    ]:
        with pytest.raises(ValueError):
            evidence.archive_boundary(source, changed)


def test_import_preservation_compares_distinct_full_snapshots_and_store_identity():
    before = snapshot()
    after = snapshot()
    assert evidence.unchanged_destination(before, after) == {
        "before": before,
        "after": after,
    }
    for changed in [
        dict(after, H=3),
        dict(after, history=[]),
        dict(after, records=[]),
        dict(after, health=dict(after["health"], api_epoch="rotated")),
    ]:
        with pytest.raises(ValueError):
            evidence.unchanged_destination(before, changed)


def test_snapshot_pages_and_final_health_must_share_one_boundary():
    base = snapshot()
    calls = []

    def get(path):
        calls.append(path)
        if path == "/api/v2/operator/health":
            return base["health"]
        if path == "/api/v2/missions":
            return base["missions"]
        if path.startswith("/api/v2/operator/records?"):
            assert "mission_id=m" in path
            return {"H": 2, "cursor": None, "items": [{"record": base["records"][0]}]}
        if path == "/api/v2/operator/records/a/history":
            return {
                "H": 2,
                "cursor": None,
                "items": [{"record": r} for r in base["history"]],
            }
        raise AssertionError(path)

    assert evidence.read_snapshot(get) == base
    assert "include_removed=true" in calls[2]

    def stale(path):
        result = get(path)
        return dict(result, H=3) if path.endswith("/history") else result

    with pytest.raises(ValueError, match="boundary"):
        evidence.read_snapshot(stale)


def test_private_browser_origin_is_identity_only_and_never_adopts_paths_or_credentials():
    assert (
        evidence.browser_origin("http://127.0.0.1:56533/") == "http://127.0.0.1:56533"
    )
    for value in [
        "file:///tmp",
        "https://user:secret@example.invalid",
        "https://example.invalid/path",
        "https://example.invalid?x=1",
        "//example.invalid",
    ]:
        with pytest.raises(ValueError):
            evidence.browser_origin(value)
    for port in [0, 65536, "56533", True]:
        with pytest.raises(ValueError):
            evidence.loopback_reader(port)


def test_snapshot_rejects_cursor_loops_and_rotated_epoch():
    base = snapshot()

    def looping(path):
        if path.endswith("/health"):
            return base["health"]
        if path.endswith("/missions"):
            return base["missions"]
        return {"H": 2, "cursor": "same-cursor", "items": []}

    with pytest.raises(ValueError, match="pagination"):
        evidence.read_snapshot(looping)
    health_reads = 0

    def rotating(path):
        nonlocal health_reads
        if path.endswith("/health"):
            health_reads += 1
            return (
                dict(base["health"], api_epoch="rotated")
                if health_reads > 1
                else base["health"]
            )
        if path.endswith("/missions"):
            return base["missions"]
        return {"H": 0, "cursor": None, "items": []}

    with pytest.raises(ValueError, match="identity"):
        evidence.read_snapshot(rotating)


def test_empty_catalog_still_reads_a_mission_filtered_page_to_pin_global_h():
    base = snapshot()
    calls = []

    def get(path):
        calls.append(path)
        if path.endswith("/health"):
            return base["health"]
        if path.endswith("/missions"):
            return []
        assert "mission_id=" in path
        return {"H": 0, "cursor": None, "items": []}

    result = evidence.read_snapshot(get)
    assert result["H"] == 0 and result["records"] == []
    assert any("include_removed=true" in path for path in calls)


def test_catalog_stub_read_times_are_not_persisted_plan_revisions():
    base = snapshot()
    reads = 0

    def get(path):
        nonlocal reads
        if path.endswith("/health"):
            return base["health"]
        if path.endswith("/missions"):
            reads += 1
            return [
                {
                    "id": "m",
                    "name": "Private mission",
                    "legs": [
                        {
                            "id": "leg-one",
                            "created_at": str(reads),
                            "updated_at": str(reads),
                        }
                    ],
                }
            ]
        return {"H": 0, "cursor": None, "items": []}

    assert evidence.read_snapshot(get)["H"] == 0
    reads = 0

    def changed_plan(path):
        result = get(path)
        if path.endswith("/missions") and reads > 1:
            result[0]["name"] = "Actually changed plan"
        return result

    with pytest.raises(ValueError, match="mission list changed"):
        evidence.read_snapshot(changed_plan)


def test_catalog_that_may_be_truncated_cannot_claim_complete_preservation():
    base = snapshot()

    def get(path):
        if path.endswith("/health"):
            return base["health"]
        return [{"id": str(index)} for index in range(10)]

    with pytest.raises(ValueError, match="complete course boundary"):
        evidence.read_snapshot(get)


def test_ready_download_reads_original_bytes_through_existing_get_only(monkeypatch):
    import http.client

    calls = []

    class Response:
        status = 200

        def read(self, limit):
            calls.append(("bound", limit))
            return b"PK-original-ready-artifact"

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1" and port == 56533 and timeout <= 15

        def request(self, method, path):
            calls.append((method, path))

        def getresponse(self):
            return Response()

        def close(self):
            calls.append(("closed", True))

    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    get = evidence.loopback_reader(56533)
    path = "/api/v2/missions/m/export-preparations/" + "a" * 32 + "/download"
    assert get(path, binary=True) == b"PK-original-ready-artifact"
    assert calls == [("GET", path), ("bound", 64 * 1024 * 1024 + 1), ("closed", True)]
    with pytest.raises(ValueError, match="ready artifact"):
        get("/api/v2/missions/m/export-preparations", binary=True)


def test_import_replacement_uses_actual_file_generation_not_mission_count():
    file = {
        "mission_id": "m",
        "device": "1",
        "inode": "10",
        "modifiedNs": "100",
        "sha256": "a" * 64,
        "size": 100,
    }
    before = {"planFiles": [file]}
    after = {"planFiles": [dict(file, inode="11", modifiedNs="101")]}
    assert evidence.installed_generation(before, after, "m")
    assert evidence.installed_generation({"planFiles": []}, after, "m")
    assert not evidence.installed_generation(before, before, "m")
    assert not evidence.installed_generation(
        before, {"planFiles": [dict(file, inode="11", sha256="b" * 64)]}, "m"
    )
    assert not evidence.installed_generation(before, {"planFiles": []}, "m")
