"""Atomic sibling state, truthful failure, and process-safe acknowledgement."""

import asyncio
import importlib
import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest
from filelock import FileLock

from app.models.route_sigmets import NoticeMutation
from tests.unit.test_route_sigmets_identity import feature

CTX = "a" * 64
OTHER = "b" * 64


def module():
    return importlib.import_module("app.services.aviation_weather.route_state")


def groups(count=1, start=0, expires=2000):
    grouping = importlib.import_module("app.services.aviation_weather.route_identity")
    return grouping.group_bulletins(
        [
            feature(
                str(i),
                bulletin_series=f"A{i}",
                valid_to_ms=expires,
                expires_at_ms=expires,
            )
            for i in range(start, start + count)
        ]
    )


def mutation(group, acknowledged, context=CTX):
    return NoticeMutation(
        context_key=context,
        notice_key=group.notice_key(context),
        semantic_digest=group.semantic_digest,
        acknowledged=acknowledged,
    )


@pytest.mark.asyncio
async def test_repeated_clear_is_idempotent_and_reopen_preserves_state(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    first = await store.reconcile(CTX, [group], 500)
    key = group.notice_key(CTX)
    assert first.records[key].attention_order == first.attention_counter == 1
    cleared = await store.set_ack(mutation(group, True), 501)
    contents = store.path.read_bytes()
    repeated = await store.set_ack(mutation(group, True), 502)
    assert repeated.state_revision == cleared.state_revision
    assert store.path.read_bytes() == contents
    reopened = await module().NoticeStore(store.path).reconcile(CTX, [group], 503)
    assert reopened.records[key].acknowledged is True
    assert reopened.state_revision == cleared.state_revision
    refreshed = await store.reconcile(CTX, groups(), 504)
    assert refreshed.records[key].attention_order == 1
    shown = await store.set_ack(mutation(group, False), 505)
    repeated_show = await store.set_ack(mutation(group, False), 506)
    assert shown.attention_order == repeated_show.attention_order == 2
    assert shown.state_revision == repeated_show.state_revision


@pytest.mark.asyncio
async def test_refresh_keeps_order_semantic_amendment_starts_pending(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    await store.reconcile(CTX, [group], 500)
    await store.set_ack(mutation(group, True), 501)
    original = await store.reconcile(CTX, [group], 502)
    assert original.records[group.notice_key(CTX)].acknowledged
    updated_feature = feature(revision="AMD", issued_at_ms=150)
    grouping = importlib.import_module("app.services.aviation_weather.route_identity")
    updated = grouping.group_bulletins([updated_feature])[0]
    state = await store.reconcile(CTX, [updated], 503)
    assert not state.records[updated.notice_key(CTX)].acknowledged
    assert state.records[updated.notice_key(CTX)].attention_order == 2


@pytest.mark.asyncio
async def test_expiry_prunes_without_feed_record_and_future_is_not_registered(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    await store.reconcile(CTX, [group], 500)
    state = await store.reconcile(CTX, [], 2000)
    assert state.records == {}
    future = await store.reconcile(CTX, groups(), 100)
    assert future.records == {}
    with pytest.raises(module().NoticeConflict):
        await store.set_ack(mutation(group, True), 2000)


@pytest.mark.asyncio
async def test_inactive_context_lru_and_record_caps(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    eligible = groups(500)
    for i in range(8):
        state = await store.reconcile(f"{i:064x}", eligible, 500 + i)
    assert len(state.contexts) == 8 and len(state.records) == 4000
    # Revisit the oldest context, then add a ninth. Context 1 is now the LRU.
    await store.reconcile("0" * 64, eligible, 510)
    state = await store.reconcile(CTX, eligible, 511)
    assert len(state.contexts) == 8 and len(state.records) == 4000
    assert "0" * 64 in state.contexts and f"{1:064x}" not in state.contexts
    assert len(store.path.read_bytes()) <= 2 * 1024**2


@pytest.mark.asyncio
async def test_capacity_pressure_never_evicts_live_current_acknowledgements(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    first = groups()[0]
    await store.reconcile(CTX, [first], 500)
    await store.set_ack(mutation(first, True), 501)
    for i in range(8):
        batch = groups(500 if i else 499, start=1 + i * 500)
        await store.reconcile(CTX, batch, 502 + i)
    before = store.path.read_bytes()
    with pytest.raises(module().NoticeCapacityError):
        await store.reconcile(CTX, groups(1, start=5000), 520)
    assert store.path.read_bytes() == before
    state = await store.reconcile(CTX, [], 520)
    assert len(state.records) == 4000
    assert state.records[first.notice_key(CTX)].acknowledged is True


@pytest.mark.asyncio
async def test_serialized_byte_cap_rejects_without_partial_commit(
    tmp_path, monkeypatch
):
    store = module().NoticeStore(tmp_path / "notices.json")
    await store.reconcile(CTX, groups(), 500)
    before = store.path.read_bytes()
    monkeypatch.setattr(module(), "MAX_STATE_BYTES", len(before) + 100)
    with pytest.raises(module().NoticeCapacityError):
        await store.reconcile(CTX, groups(2), 501)
    assert store.path.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("contents", [b"{invalid", b"{}", b'{"schema":"wrong"}'])
async def test_corrupt_file_is_unchanged_and_not_reported_acknowledged(
    tmp_path, contents
):
    path = tmp_path / "notices.json"
    path.write_bytes(contents)
    with pytest.raises(module().NoticeStoreUnavailable):
        await module().NoticeStore(path).reconcile(CTX, groups(), 500)
    assert path.read_bytes() == contents


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["replace", "fsync"])
async def test_disk_failure_preserves_bytes_revision_and_removes_temp(
    tmp_path, monkeypatch, operation
):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    state = await store.reconcile(CTX, [group], 500)
    before = store.path.read_bytes()

    def full_disk(*args):
        raise OSError("disk full at secret path")

    with monkeypatch.context() as patch:
        patch.setattr(os, operation, full_disk)
        with pytest.raises(
            module().NoticeStoreUnavailable,
            match="^Route SIGMET notice state unavailable$",
        ):
            await store.set_ack(mutation(group, True), 501)
    assert store.path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    reopened = await store.reconcile(CTX, [group], 502)
    assert reopened.state_revision == state.state_revision
    assert not reopened.records[group.notice_key(CTX)].acknowledged


def record_child(child):
    ledger = os.environ.get("TASK3_PROCESS_LEDGER")
    if ledger:
        with Path(ledger).open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "kind": "multiprocessing",
                        "pid": child.pid,
                        "pgid": os.getpgid(child.pid),
                        "owner": os.getpid(),
                    }
                )
                + "\n"
            )


async def close_child(child):
    if child.is_alive():
        child.terminate()
        await asyncio.to_thread(child.join, 5)
    if child.is_alive():
        child.kill()
        await asyncio.to_thread(child.join, 5)
    assert not child.is_alive()
    child.close()


def hold_lock(path, ready, release):
    with FileLock(f"{path}.lock"):
        ready.set()
        release.wait(10)


@pytest.mark.asyncio
async def test_lock_timeout_is_one_second_and_does_not_block_event_loop(tmp_path):
    path = tmp_path / "notices.json"
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    child = ctx.Process(target=hold_lock, args=(str(path), ready, release))
    child.start()
    record_child(child)
    try:
        assert await asyncio.to_thread(ready.wait, 5)
        store = module().NoticeStore(path)
        started = time.monotonic()
        task = asyncio.create_task(store.reconcile(CTX, groups(), 500))
        await asyncio.sleep(0.1)
        assert not task.done()  # Event loop ran while the other process held the lock.
        with pytest.raises(module().NoticeStoreUnavailable):
            await task
        assert 0.9 <= time.monotonic() - started < 2.5
        assert not path.exists()
    finally:
        release.set()
        await asyncio.to_thread(child.join, 5)
        await close_child(child)


def clear_from_process(path, group, gate):
    gate.wait(10)
    store = module().NoticeStore(Path(path))
    store.set_ack_sync(mutation(group, True), 501)


@pytest.mark.asyncio
async def test_two_process_clear_has_one_revision_and_atomic_valid_json(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    first = await store.reconcile(CTX, [group], 500)
    ctx = multiprocessing.get_context("spawn")
    gate = ctx.Event()
    children = [
        ctx.Process(target=clear_from_process, args=(str(store.path), group, gate))
        for _ in range(2)
    ]
    try:
        for child in children:
            child.start()
            record_child(child)
        gate.set()
        for child in children:
            await asyncio.to_thread(child.join, 8)
            assert child.exitcode == 0
        state = await store.reconcile(CTX, [group], 502)
        assert state.state_revision == first.state_revision + 1
        assert state.records[group.notice_key(CTX)].acknowledged is True
        assert (
            json.loads(store.path.read_text())["state_revision"] == state.state_revision
        )
    finally:
        for child in children:
            await close_child(child)


@pytest.mark.asyncio
async def test_validator_runs_inside_notice_lock_and_failure_does_not_write(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    group = groups()[0]
    await store.reconcile(CTX, [group], 500)
    before = store.path.read_bytes()

    def obsolete():
        assert store.lock.is_locked
        raise module().NoticeConflict("Superseded notice")

    with pytest.raises(module().NoticeConflict):
        await store.set_ack(mutation(group, True), 501, validate=obsolete)
    assert store.path.read_bytes() == before
    with pytest.raises(module().NoticeConflict):
        await store.set_ack(mutation(group, True, OTHER), 501)


@pytest.mark.asyncio
async def test_sibling_settings_bytes_are_untouched(tmp_path):
    settings = tmp_path / "settings.json"
    contents = (
        b'{"sigmet":false,"sigmet_intersecting_only":false,"winds":false,"revision":7}'
    )
    settings.write_bytes(contents)
    store = module().NoticeStore(tmp_path / "route-sigmet-state.json")
    group = groups()[0]
    await store.reconcile(CTX, [group], 500)
    await store.set_ack(mutation(group, True), 501)
    assert settings.read_bytes() == contents


@pytest.mark.asyncio
async def test_lru_uses_visits_even_when_clock_ticks_tie_or_move_back(tmp_path):
    store = module().NoticeStore(tmp_path / "notices.json")
    for i in range(8):
        await store.reconcile(f"{i:064x}", [], 500)
    await store.reconcile("0" * 64, [], 499)
    state = await store.reconcile(CTX, [], 499)
    assert "0" * 64 in state.contexts
    assert f"{1:064x}" not in state.contexts
