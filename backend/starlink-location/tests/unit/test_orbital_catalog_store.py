import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest

from app.services.orbital_catalog_store import OrbitalCatalogStore

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_cross_process_style_stores_share_atomic_attempt_lock(tmp_path):
    barrier = Barrier(20)

    def attempt(_):
        store = OrbitalCatalogStore(tmp_path)
        barrier.wait(timeout=5)
        return store.reserve_attempt(NOW)

    with ThreadPoolExecutor(max_workers=20) as pool:
        assert sum(pool.map(attempt, range(20))) == 1


def test_partial_write_keeps_old_catalog(tmp_path, monkeypatch):
    store = OrbitalCatalogStore(tmp_path)
    store.save_catalog(
        {
            "generation": "good",
            "objects": [],
            "acquired_at": NOW.isoformat(),
            "rejected_count": 0,
            "truncated_count": 0,
        }
    )

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("app.services.orbital_catalog_store.os.replace", fail)
    with pytest.raises(OSError):
        store.save_catalog({"generation": "bad"})
    assert store.read_catalog()["generation"] == "good"
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_state_with_existing_catalog_cannot_reset_clock(tmp_path):
    (tmp_path / "catalog.json").write_text('{"objects": []}')
    store = OrbitalCatalogStore(tmp_path)
    assert store.reserve_attempt(NOW) is False
    assert store.read_state()["suspended"] is True


def _reserve_from_process(path, barrier, results):
    store = OrbitalCatalogStore(path)
    barrier.wait(timeout=10)
    results.put(store.reserve_attempt(NOW))


def test_separate_processes_cannot_make_simultaneous_attempts(tmp_path):
    context = multiprocessing.get_context("spawn")
    barrier, results = context.Barrier(2), context.Queue()
    processes = [
        context.Process(target=_reserve_from_process, args=(tmp_path, barrier, results))
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        assert sorted(results.get(timeout=15) for _ in processes) == [False, True]
        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
