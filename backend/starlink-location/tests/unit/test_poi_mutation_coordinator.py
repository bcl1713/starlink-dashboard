"""Concurrency and failure contracts for durable POI mutations."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.models.poi import POICreate
from app.services.poi_manager import POIManager


def _payload(name: str) -> POICreate:
    return POICreate(name=name, latitude=1.0, longitude=2.0)


def test_disjoint_manager_creates_survive_concurrent_fresh_reopen(tmp_path):
    """Separate stale managers must apply creates to the fresh locked snapshot."""
    pois_file = tmp_path / "pois.json"
    first = POIManager(pois_file)
    second = POIManager(pois_file)
    barrier = threading.Barrier(2)

    def create(manager: POIManager, name: str) -> str:
        barrier.wait()
        return manager.create_poi(_payload(name)).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(
            executor.map(
                lambda item: create(*item), [(first, "first"), (second, "second")]
            )
        )

    reopened = POIManager(pois_file)
    assert {poi.id for poi in reopened.list_pois()} == set(ids)


def test_shared_manager_readers_get_stable_copies_while_writers_commit(tmp_path):
    """Readers cannot observe or mutate the manager's live POI dictionary."""
    manager = POIManager(tmp_path / "pois.json")
    start = threading.Barrier(6)

    def writer(index: int) -> None:
        start.wait()
        for sequence in range(10):
            manager.create_poi(_payload(f"writer-{index}-{sequence}"))

    def reader() -> None:
        start.wait()
        for _ in range(100):
            snapshot = manager.list_pois()
            for poi in snapshot:
                poi.name = "caller-owned-copy"

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(writer, index) for index in range(2)]
        futures.extend(executor.submit(reader) for _ in range(4))
        for future in futures:
            future.result()

    assert manager.count_pois() == 20
    assert all(poi.name != "caller-owned-copy" for poi in manager.list_pois())


def test_coalesced_callers_wait_for_one_durable_snapshot(tmp_path, monkeypatch):
    """Barriered callers share one bounded commit and return only after it writes."""
    manager = POIManager(tmp_path / "pois.json")
    original_write = manager._write_json_durable
    writes = 0
    writes_lock = threading.Lock()

    def counted_write(data):
        nonlocal writes
        with writes_lock:
            writes += 1
        original_write(data)

    monkeypatch.setattr(manager, "_write_json_durable", counted_write)
    barrier = threading.Barrier(10)

    def create(index: int) -> str:
        barrier.wait()
        return manager.create_poi(_payload(f"coalesced-{index}")).id

    with ThreadPoolExecutor(max_workers=10) as executor:
        ids = list(executor.map(create, range(10)))

    assert len(ids) == 10
    assert writes == 1
    assert {poi.id for poi in POIManager(manager.pois_file).list_pois()} == set(ids)


def test_failed_replace_leaves_cache_unchanged_and_corrupt_storage_fails_closed(
    tmp_path, monkeypatch
):
    """A failed replace never acknowledges/cache-publishes and corrupt JSON is not reset."""
    pois_file = tmp_path / "pois.json"
    manager = POIManager(pois_file)
    original = manager.create_poi(_payload("original"))

    def fail_write(data):
        raise OSError("disk full")

    monkeypatch.setattr(manager, "_write_json_durable", fail_write)
    with pytest.raises(OSError, match="disk full"):
        manager.create_poi(_payload("not-committed"))
    assert [poi.id for poi in manager.list_pois()] == [original.id]

    pois_file.write_text("{ not json")
    corrupt_manager = POIManager(pois_file)
    with pytest.raises(ValueError, match="corrupt"):
        corrupt_manager.create_poi(_payload("must-not-reset"))
    assert pois_file.read_text() == "{ not json"
