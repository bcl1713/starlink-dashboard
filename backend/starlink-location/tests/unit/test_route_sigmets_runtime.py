"""Shared real source admission, UTC lifecycle and revision-scoped persistence."""

import asyncio
import copy
import importlib
import sys

import pytest

from app.models.route_sigmets import NoticeMutation, RouteContext
from app.services.aviation_weather.route_context import route_context_key
from app.services.aviation_weather.route_state import NoticeConflict, NoticeStore
from app.services.aviation_weather.runtime import AviationWeatherService
from app.services.aviation_weather.settings import AviationSettingsStore
from tests.unit.test_aviation_weather_runtime import Source
from tests.unit.test_route_sigmets_decode import children  # noqa: F401
from tests.unit.test_route_sigmets_identity import feature


@pytest.fixture(autouse=True)
async def owned_geometry_children(children):  # noqa: F811
    # Keep all runtime tests on the real process boundary with explicit ownership
    # and teardown assertions, including failing red tests.
    yield children


def setup_service(tmp_path):
    module = importlib.import_module("app.services.aviation_weather.route_runtime")
    now, mono = [1000], [0]
    reports = [feature()]
    store = AviationSettingsStore(tmp_path / "aviation.json")
    source = Source()

    async def normalize(layer, body, instant):
        return {
            "type": "FeatureCollection",
            "source_id": "awc",
            "retrieved_at_ms": instant,
            "feed_completeness": "complete",
            "omitted_features": 0,
            "features": copy.deepcopy(reports),
        }

    weather = AviationWeatherService(
        store,
        source,
        utc_ms=lambda: now[0],
        monotonic=lambda: mono[0],
        normalize=normalize,
    )
    points = [[1, 1], [2, 1]]
    context = [
        RouteContext(
            context_key=route_context_key("ordinary", "route", None, None, points),
            source="ordinary",
            route_id="route",
            route_name="Test",
            runtime_id=None,
            run_id=None,
            points=points,
        )
    ]
    service = module.RouteSigmetService(
        weather, NoticeStore(tmp_path / "notices.json"), lambda: context[0]
    )
    return service, weather, store, source, now, mono, reports, context


async def close(service, weather):
    await service.aclose()
    await weather.aclose()


def mutation(snapshot, acknowledged=True):
    entry = snapshot.entries[0]
    return NoticeMutation(
        context_key=snapshot.context.context_key,
        notice_key=entry.notice_key,
        semantic_digest=entry.semantic_digest,
        acknowledged=acknowledged,
    )


async def test_off_and_no_route_never_match_but_all_mode_still_acquires(tmp_path):
    service, weather, store, source, _, _, _, context = setup_service(tmp_path)
    try:
        assert (await service.read()).status == "off"
        assert source.calls == []
        store.update({"sigmet": True, "metar": True})
        context[0] = None
        assert (await service.read()).status == "no-route"
        assert source.calls == ["sigmet"]
        product, collection = await weather.read_layer("sigmet")
        assert product.state == "ready" and collection["features"]
    finally:
        await close(service, weather)


async def test_first_load_clear_show_refresh_restart_and_disable(tmp_path):
    service, weather, store, source, now, mono, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        assert len(first.entries) == 1 and not first.entries[0].acknowledged
        clear = await service.acknowledge(mutation(first))
        assert (
            await service.acknowledge(mutation(first))
        ).state_revision == clear.state_revision
        assert (await service.read()).entries[0].acknowledged
        again = await service.acknowledge(mutation(first, False))
        assert again.attention_order > clear.attention_order
        await service.acknowledge(mutation(first))
        now[0], mono[0] = 1100, 301
        refreshed = await service.read()
        assert refreshed.sigmet_product.instance_id != first.sigmet_product.instance_id
        assert refreshed.entries[0].acknowledged
        assert refreshed.entries[0].notice_key == first.entries[0].notice_key
        await service.aclose()
        module = importlib.import_module("app.services.aviation_weather.route_runtime")
        service = module.RouteSigmetService(
            weather, NoticeStore(tmp_path / "notices.json"), service.context_provider
        )
        assert (await service.read()).entries[0].acknowledged
        settings = store.update({"sigmet": False})
        await asyncio.gather(
            weather.settings_changed(settings), service.settings_changed(settings)
        )
        assert (await service.read()).status == "off"
        assert source.calls == ["sigmet", "sigmet"]
    finally:
        await close(service, weather)


async def test_validity_boundaries_without_refresh_and_stale_original_deadline(
    tmp_path,
):
    service, weather, store, source, now, _mono, reports, _ = setup_service(tmp_path)
    try:
        reports[0]["properties"].update(
            valid_from_ms=1200, valid_to_ms=900000, expires_at_ms=900000
        )
        store.update({"sigmet": True})
        future = await service.read()
        assert not future.entries and future.future_feature_ids == ["a"]
        now[0] = 1200
        current = await service.read()
        assert len(current.entries) == 1
        now[0] = 602000
        stale = await service.read()
        assert stale.status == "stale" and stale.entries
        assert stale.sigmet_product.expires_at_ms == 900000
        now[0] = 900000
        assert not (await service.read()).entries
        assert source.calls == ["sigmet"]
    finally:
        await close(service, weather)


async def test_old_revision_clear_returns_conflict_and_route_edit_isolated(tmp_path):
    service, weather, store, _, now, mono, reports, context = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        reports[0]["properties"].update(
            revision="AMD", issued_at_ms=150, amends="TEST/FIR1/A1"
        )
        mono[0], now[0] = 301, 1100
        replacement = await service.read()
        with pytest.raises(NoticeConflict):
            await service.acknowledge(mutation(first))
        assert not replacement.entries[0].acknowledged
        context[0] = context[0].model_copy(update={"context_key": "a" * 64})
        with pytest.raises(NoticeConflict):
            await service.acknowledge(mutation(replacement))
        assert not (await service.read()).entries[0].acknowledged
    finally:
        await close(service, weather)


async def test_unlocated_and_unknown_lineage_remain_explicit(tmp_path):
    service, weather, store, _, _, _, reports, _ = setup_service(tmp_path)
    try:
        reports[0]["properties"]["issuer"] = None
        missing = feature("missing", bulletin_series="B2")
        missing["geometry"] = None
        reports.append(missing)
        store.update({"sigmet": True})
        result = await service.read()
        assert result.status == "incomplete" and not result.complete
        assert result.entries[0].identity_uncertain
        assert {(item.feature_id, item.reason) for item in result.unresolved} == {
            ("a", "identity-uncertain"),
            ("missing", "unlocated"),
        }
    finally:
        await close(service, weather)


async def test_duplicate_readers_share_admission_and_geometry_cache(
    tmp_path, monkeypatch
):
    from app.services.aviation_weather import route_decode

    original, calls = route_decode.evaluate_in_worker, []

    async def evaluate(context, collection):
        calls.append(collection)
        return await original(context, collection)

    monkeypatch.setattr(route_decode, "evaluate_in_worker", evaluate)
    service, weather, store, source, now, mono, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        results = await asyncio.gather(service.read(), service.read())
        assert results[0].entries == results[1].entries
        assert len(calls) == 1 and source.calls == ["sigmet"]
        now[0], mono[0] = 1100, 301
        assert (await service.read()).entries
        assert len(calls) == 1 and source.calls == ["sigmet", "sigmet"]
    finally:
        await close(service, weather)


async def test_disable_cancels_matching_and_reaps_before_return(tmp_path, monkeypatch):
    from app.services.aviation_weather import route_decode

    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def blocked(context, collection):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    monkeypatch.setattr(route_decode, "evaluate_in_worker", blocked)
    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        read = asyncio.create_task(service.read())
        await asyncio.wait_for(entered.wait(), 2)
        await weather.settings_changed(store.update({"sigmet": False}))
        assert cleaned.is_set()
        result = await read
        assert result.status == "off" and not result.entries
    finally:
        await close(service, weather)


async def test_late_route_completion_suppresses_old_notices(tmp_path, monkeypatch):
    from app.services.aviation_weather import route_decode

    entered, release = asyncio.Event(), asyncio.Event()
    original = route_decode.evaluate_in_worker

    async def blocked(context, collection):
        entered.set()
        await release.wait()
        return await original(context, collection)

    monkeypatch.setattr(route_decode, "evaluate_in_worker", blocked)
    service, weather, store, _, _, _, _, context = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        read = asyncio.create_task(service.read())
        await asyncio.wait_for(entered.wait(), 2)
        context[0] = context[0].model_copy(update={"context_key": "b" * 64})
        release.set()
        result = await read
        assert result.context.context_key == "b" * 64
        assert result.status == "evaluating" and not result.entries
    finally:
        release.set()
        await close(service, weather)


async def test_cancellation_boundary_rechecks_current_utc_without_refresh(tmp_path):
    service, weather, store, _, now, _, reports, _ = setup_service(tmp_path)
    try:
        reports[0]["properties"].update(valid_to_ms=9000, expires_at_ms=9000)
        reports.append(
            feature(
                "cancel",
                cancelled=True,
                valid_from_ms=1300,
                valid_to_ms=9000,
                expires_at_ms=9000,
                cancellation_target={
                    "series": "A1",
                    "valid_from_ms": 200,
                    "valid_to_ms": 9000,
                },
            )
        )
        reports[-1]["geometry"] = None
        store.update({"sigmet": True})
        first = await service.read()
        assert len(first.entries) == 1
        now[0] = 1300
        assert not (await service.read()).entries
        with pytest.raises(NoticeConflict):
            await service.acknowledge(mutation(first))
    finally:
        await close(service, weather)


async def test_utc_boundary_during_notice_lock_wait_cannot_publish_old_set(
    tmp_path, monkeypatch
):
    service, weather, store, _, now, _, reports, _ = setup_service(tmp_path)
    try:
        reports[0]["properties"]["valid_from_ms"] = 1200
        store.update({"sigmet": True})
        original = service.store.reconcile_sync

        def boundary(*args, **kwargs):
            now[0] = 1200
            return original(*args, **kwargs)

        monkeypatch.setattr(service.store, "reconcile_sync", boundary)
        result = await service.read()
        assert result.status == "evaluating" and not result.entries
        assert not service.store.path.exists()
    finally:
        await close(service, weather)


async def test_failed_source_is_unavailable_and_preserves_notice_file(tmp_path):
    service, weather, store, source, now, mono, _, _ = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        await service.acknowledge(mutation(first))
        saved = service.store.path.read_bytes()
        source.fail = True
        now[0], mono[0] = 2000, 301
        assert (await service.read()).status == "unavailable"
        assert service.store.path.read_bytes() == saved
    finally:
        await close(service, weather)


async def test_split_group_keeps_known_spans_and_unknown_portions(tmp_path):
    service, weather, store, _, _, _, reports, _ = setup_service(tmp_path)
    try:
        missing = copy.deepcopy(reports[0])
        missing["id"], missing["geometry"] = "split-unknown", None
        reports.append(missing)
        store.update({"sigmet": True})
        result = await service.read()
        assert len(result.entries) == 1 and result.entries[0].spans
        assert result.entries[0].feature_ids == ["a", "split-unknown"]
        assert [(u.feature_id, u.reason) for u in result.unresolved] == [
            ("split-unknown", "unlocated")
        ]
        assert result.status == "incomplete"
    finally:
        await close(service, weather)


async def test_route_change_after_write_returns_conflict_and_new_route_stays_pending(
    tmp_path, monkeypatch
):
    service, weather, store, _, _, _, _, context = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        original = service.store.set_ack_sync

        def replacement(*args, **kwargs):
            confirmed = original(*args, **kwargs)
            context[0] = context[0].model_copy(update={"context_key": "c" * 64})
            return confirmed

        monkeypatch.setattr(service.store, "set_ack_sync", replacement)
        with pytest.raises(NoticeConflict):
            await service.acknowledge(mutation(first))
        assert not (await service.read()).entries[0].acknowledged
    finally:
        await close(service, weather)


async def test_feed_replacement_inside_notice_lock_rejects_late_clear(
    tmp_path, monkeypatch
):
    import threading

    service, weather, store, _, now, mono, reports, _ = setup_service(tmp_path)
    started, release = threading.Event(), threading.Event()
    task = None
    try:
        store.update({"sigmet": True})
        first = await service.read()
        original = service.store.set_ack_sync

        def blocked(*args, **kwargs):
            started.set()
            assert release.wait(3)
            return original(*args, **kwargs)

        monkeypatch.setattr(service.store, "set_ack_sync", blocked)
        task = asyncio.create_task(service.acknowledge(mutation(first)))
        async with asyncio.timeout(3):
            while not started.is_set():
                await asyncio.sleep(0.01)
        reports[0]["properties"].update(raw_text="NEW REVISION", revision="AMD")
        now[0], mono[0] = 1100, 301
        await weather.read_layer("sigmet")
        release.set()
        with pytest.raises(NoticeConflict):
            await task
        assert not (await service.read()).entries[0].acknowledged
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await close(service, weather)


@pytest.mark.parametrize("stop", ["cancel", "disable", "shutdown"])
async def test_real_matching_worker_reaped_after_repeated_cancellation(
    tmp_path, monkeypatch, stop
):
    from app.services.aviation_weather import route_decode

    ready = tmp_path / "worker-ready"
    program = f"import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path({str(ready)!r}).touch(); time.sleep(60)"
    monkeypatch.setattr(route_decode, "WORKER_COMMAND", (sys.executable, "-c", program))
    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    read, stopping = None, None
    try:
        store.update({"sigmet": True})
        read = asyncio.create_task(service.read())
        async with asyncio.timeout(3):
            while not ready.exists():
                await asyncio.sleep(0.01)
        if stop == "cancel":
            stopping = read
        elif stop == "disable":
            stopping = asyncio.create_task(
                weather.settings_changed(store.update({"sigmet": False}))
            )
        else:
            stopping = asyncio.create_task(service.aclose())
        if stop == "cancel":
            read.cancel()
        await asyncio.sleep(0.05)
        stopping.cancel()
        await asyncio.sleep(0.05)
        assert not stopping.done()
        await asyncio.gather(stopping, read, return_exceptions=True)
    finally:
        for task in (read, stopping):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(t for t in (read, stopping) if t is not None), return_exceptions=True
        )
        await close(service, weather)


async def test_active_leg_lock_contention_is_bounded_and_does_not_block_loop(tmp_path):
    import threading

    from filelock import Timeout

    from app.mission.storage import get_active_leg_lock
    from app.services.overview_weather.protocol import WeatherUnavailable

    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def holder():
        with get_active_leg_lock():
            entered.set()
            release.wait(4)

    thread = threading.Thread(target=holder)
    thread.start()
    try:
        store.update({"sigmet": True})
        assert await asyncio.to_thread(entered.wait, 1)
        read = asyncio.create_task(service.read())
        await asyncio.sleep(0.02)
        assert not read.done()
        with pytest.raises((Timeout, WeatherUnavailable)):
            async with asyncio.timeout(2):
                await read
    finally:
        release.set()
        await asyncio.to_thread(thread.join, 2)
        await close(service, weather)


async def test_matching_delay_uses_current_staleness_with_original_deadlines(
    tmp_path, monkeypatch
):
    from app.services.aviation_weather import route_decode

    original = route_decode.evaluate_in_worker
    service, weather, store, _, now, _, reports, _ = setup_service(tmp_path)

    async def delayed(context, collection):
        result = await original(context, collection)
        now[0] = 602000
        return result

    monkeypatch.setattr(route_decode, "evaluate_in_worker", delayed)
    try:
        reports[0]["properties"].update(valid_to_ms=900000, expires_at_ms=900000)
        store.update({"sigmet": True})
        result = await service.read()
        assert result.status == "stale" and result.sigmet_product.state == "stale"
        assert result.sigmet_product.fresh_until_ms == 601000
        assert result.sigmet_product.expires_at_ms == 900000
    finally:
        await close(service, weather)


@pytest.mark.parametrize("change", ["route", "disable"])
async def test_source_wait_revalidates_no_route_and_disable(tmp_path, change):
    service, weather, store, source, _, _, _, context = setup_service(tmp_path)
    read = None
    try:
        store.update({"sigmet": True})
        original_context = context[0]
        context[0] = None
        source.gate = asyncio.Event()
        read = asyncio.create_task(service.read())
        async with asyncio.timeout(3):
            while not source.calls:
                await asyncio.sleep(0.01)
        if change == "route":
            context[0] = original_context
        else:
            await weather.settings_changed(store.update({"sigmet": False}))
        source.gate.set()
        result = await read
        assert result.status == ("evaluating" if change == "route" else "off")
        assert not result.entries
        if change == "route":
            assert result.context.context_key == original_context.context_key
    finally:
        if read is not None:
            read.cancel()
            await asyncio.gather(read, return_exceptions=True)
        await close(service, weather)


async def test_semantic_content_cache_ignores_ring_order_and_retains_only_two(
    tmp_path, monkeypatch
):
    from app.services.aviation_weather import route_decode

    original, calls = route_decode.evaluate_in_worker, []

    async def evaluate(context, collection):
        calls.append(context.context_key)
        return await original(context, collection)

    monkeypatch.setattr(route_decode, "evaluate_in_worker", evaluate)
    service, weather, store, _, now, mono, reports, context = setup_service(tmp_path)
    try:
        store.update({"sigmet": True})
        first = await service.read()
        reports[0]["geometry"]["coordinates"][0] = [
            [3, 3],
            [3, 0],
            [0, 0],
            [0, 3],
            [3, 3],
        ]
        now[0], mono[0] = 1100, 301
        assert (await service.read()).entries[0].notice_key == first.entries[
            0
        ].notice_key
        assert len(calls) == 1
        original_context = context[0]
        for key in ("d", "e"):
            context[0] = original_context.model_copy(update={"context_key": key * 64})
            assert (await service.read()).entries
        context[0] = original_context
        assert (await service.read()).entries
        assert len(calls) == 4
    finally:
        await close(service, weather)


async def test_disable_during_grouping_cannot_start_late_matching_work(
    tmp_path, monkeypatch
):
    import threading

    from app.services.aviation_weather import route_decode, route_runtime

    original_groups, original_worker = (
        route_runtime.group_bulletins,
        route_decode.evaluate_in_worker,
    )
    entered, release = threading.Event(), threading.Event()
    calls = []

    def blocked(features):
        entered.set()
        assert release.wait(3)
        return original_groups(features)

    async def evaluate(context, collection):
        calls.append(context.context_key)
        return await original_worker(context, collection)

    monkeypatch.setattr(route_runtime, "group_bulletins", blocked)
    monkeypatch.setattr(route_decode, "evaluate_in_worker", evaluate)
    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    read = None
    try:
        store.update({"sigmet": True})
        read = asyncio.create_task(service.read())
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        await weather.settings_changed(store.update({"sigmet": False}))
        release.set()
        assert (await read).status == "off"
        assert calls == []
    finally:
        release.set()
        if read is not None:
            await asyncio.gather(read, return_exceptions=True)
        await close(service, weather)


async def test_read_layer_settings_lock_does_not_block_event_loop(tmp_path):
    import threading

    from filelock import Timeout

    service, weather, store, _, _, _, _, _ = setup_service(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def hold():
        with store.lock:
            entered.set()
            release.wait(3)

    holder = threading.Thread(target=hold)
    holder.start()
    read = None
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        read = asyncio.create_task(weather.read_layer("sigmet"))
        started = asyncio.get_running_loop().time()
        await asyncio.sleep(0.02)
        assert asyncio.get_running_loop().time() - started < 0.3
        with pytest.raises(Timeout):
            await read
    finally:
        release.set()
        await asyncio.to_thread(holder.join, 1)
        if read is not None:
            await asyncio.gather(read, return_exceptions=True)
        await close(service, weather)


async def test_late_old_route_grouping_cannot_supersede_current_matching(
    tmp_path, monkeypatch
):
    import threading

    from app.services.aviation_weather import route_decode, route_runtime

    original_groups, original_worker = (
        route_runtime.group_bulletins,
        route_decode.evaluate_in_worker,
    )
    grouped, release_group = threading.Event(), threading.Event()
    matching, release_match, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    grouping_count, admitted = [0], []
    service, weather, store, _, _, _, _, context = setup_service(tmp_path)
    ordinary = context[0]
    current_key = "b" * 64

    def group(features):
        grouping_count[0] += 1
        if grouping_count[0] == 1:
            grouped.set()
            assert release_group.wait(4)
        return original_groups(features)

    async def evaluate(route, collection):
        admitted.append(route.context_key)
        if route.context_key == current_key:
            matching.set()
            try:
                await release_match.wait()
                return await original_worker(route, collection)
            finally:
                cleaned.set()
        return await original_worker(route, collection)

    monkeypatch.setattr(route_runtime, "group_bulletins", group)
    monkeypatch.setattr(route_decode, "evaluate_in_worker", evaluate)
    tasks = []
    try:
        store.update({"sigmet": True})
        tasks.append(asyncio.create_task(service.read()))
        async with asyncio.timeout(2):
            while not grouped.is_set():
                await asyncio.sleep(0.01)
        context[0] = ordinary.model_copy(update={"context_key": current_key})
        tasks.append(asyncio.create_task(service.read()))
        await asyncio.wait_for(matching.wait(), 2)
        release_group.set()
        assert not (await tasks[0]).entries
        assert admitted == [current_key]
        assert not cleaned.is_set() and not tasks[1].done()
        release_match.set()
        assert (await tasks[1]).entries
    finally:
        release_group.set()
        release_match.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close(service, weather)


@pytest.mark.parametrize("selection", ["cached", "no-route"])
async def test_selection_change_reaps_incompatible_worker_even_without_admission(
    tmp_path, monkeypatch, owned_geometry_children, selection
):
    from app.services.aviation_weather import route_decode

    service, weather, store, _, _, _, _, context = setup_service(tmp_path)
    original = context[0]
    ready = tmp_path / "superseded-worker-ready"
    read = None
    try:
        store.update({"sigmet": True})
        assert (await service.read()).entries
        program = (
            f"import pathlib,time; pathlib.Path({str(ready)!r}).touch(); time.sleep(60)"
        )
        monkeypatch.setattr(
            route_decode, "WORKER_COMMAND", (sys.executable, "-c", program)
        )
        context[0] = original.model_copy(update={"context_key": "f" * 64})
        read = asyncio.create_task(service.read())
        async with asyncio.timeout(2):
            while not ready.exists():
                await asyncio.sleep(0.01)
        child = owned_geometry_children[-1]
        assert child.returncode is None
        context[0] = original if selection == "cached" else None
        current = await service.read()
        assert current.status == ("ready" if selection == "cached" else "no-route")
        assert child.returncode is not None
        assert not (await read).entries
    finally:
        if read is not None:
            read.cancel()
            await asyncio.gather(read, return_exceptions=True)
        await close(service, weather)
