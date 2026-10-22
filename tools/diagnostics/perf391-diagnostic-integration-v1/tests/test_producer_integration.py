"""Exact A/C coordinator, replay collect, producer loop and in-place metric bodies."""

import asyncio
import contextlib
import math
import os
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from backend_support import functions, module_at, modules, probe, roots

import contract


class Log:
    def __getattr__(self, _):
        return lambda *a, **kw: None


class ProducerTests(unittest.TestCase):
    def test_actual_coordinator_success_retained_and_error(self):
        for role in ("A", "C"):
            for case in ("normal", "retained", "exception", "replay_exception"):
                outputs = []
                for patched in (False, True):
                    root = roots(role)[patched]
                    gate = module_at(
                        root, "app/mission/repository_gate.py"
                    ).RepositoryGate
                    admission = module_at(root, "app/mission/input_admission.py")
                    import tempfile

                    with tempfile.TemporaryDirectory(
                        prefix="perf391-stage2-coordinator-"
                    ) as tmp:
                        lock = gate(tmp + "/gate")
                        new = NS(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
                        old = (
                            NS(timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc))
                            if case == "retained"
                            else None
                        )
                        effects = []

                        def generate(frame):
                            effects.append("generate")
                            if case != "normal":
                                raise ValueError("sensor")
                            return new

                        obj = NS(
                            _last_valid_telemetry=old,
                            _update_route_following=lambda: effects.append("route"),
                            _generate_telemetry=generate,
                        )
                        ns = functions(
                            root,
                            "app/simulation/coordinator.py",
                            ["update"],
                            {"model_input_write": admission.model_input_write},
                            cls="SimulationCoordinator",
                        )
                        probe.configure(role, "offline")
                        with modules(
                            **{
                                "app.mission.storage": {
                                    "get_active_leg_lock": lambda: lock
                                }
                            }
                        ), probe.operation("tick", "tick"):
                            try:
                                result = ns["update"](
                                    obj,
                                    replay_frame=(
                                        object() if case == "replay_exception" else None
                                    ),
                                )
                                value = (
                                    "new" if result is new else "retained",
                                    result.timestamp.isoformat(),
                                )
                            except ValueError as error:
                                value = (type(error).__name__, str(error))
                        outputs.append(
                            (
                                value,
                                effects,
                                lock.is_locked,
                                obj._last_valid_telemetry is old,
                            )
                        )
                        events = probe.drain()
                        if patched:
                            ends = [
                                e for e in events if e["phase"] == "collection.return"
                            ]
                            self.assertEqual(len(ends), 1)
                            self.assertEqual(
                                ends[0]["outcome"],
                                (
                                    "error"
                                    if case in ("exception", "replay_exception")
                                    else "ok"
                                ),
                            )
                            contract.validate_stream(events)
                self.assertEqual(outputs[0], outputs[1], (role, case))

    def test_replay_commit_order_compensation_and_paused(self):
        for role in ("A", "C"):
            for case in (
                "advance",
                "paused",
                "no_plan",
                "callback_error",
                "commit_error",
                "collection_error",
            ):
                outputs = []
                for patched in (False, True):
                    root = roots(role)[patched]
                    frames = module_at(
                        roots("C")[patched], "app/core/metrics/frames.py"
                    )
                    store = frames.FrameStore(())
                    effects = []
                    plan = object()
                    frame = object()
                    status = NS(revision=1)
                    tick = NS(frame=frame, plan=plan, status=status)
                    telemetry = NS(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
                    runtime = NS(
                        selected_plan=lambda: None if case == "no_plan" else plan,
                        prepare_tick=lambda: None if case == "paused" else tick,
                        frame=lambda: frame,
                        fail=lambda *a: effects.append("runtime.fail"),
                    )

                    def commit(value):
                        effects.append("commit")
                        if case == "commit_error":
                            raise ValueError("commit failed")

                    runtime.commit_tick = commit

                    def collect(**kwargs):
                        effects.append("collect")
                        if case == "collection_error":
                            raise ValueError("collection failed")
                        return telemetry

                    coordinator = NS(
                        checkpoint_telemetry=lambda: effects.append("checkpoint"),
                        restore_telemetry=lambda cp: effects.append("restore"),
                        update=collect,
                        get_config=lambda: NS(model_dump_json=lambda: "config"),
                    )
                    flight = NS(
                        checkpoint=lambda: effects.append("flight.checkpoint"),
                        apply_simulation_frame=lambda *a: effects.append(
                            "flight.apply"
                        ),
                        restore_checkpoint=lambda cp: effects.append("flight.restore"),
                    )

                    def publish(value, candidate):
                        effects.append("inplace" if role == "A" else "prepare")
                        if case == "callback_error":
                            raise ValueError("callback failed")
                        return None

                    self_obj = NS(
                        runtime=runtime,
                        status=lambda: status,
                        publish_committed_metrics=lambda *a: effects.append(
                            "post_commit_publish"
                        ),
                    )

                    def paused_tick(*args):
                        return NS(frame=frame, plan=plan, status=status)

                    env = {
                        "get_active_leg_lock": contextlib.nullcontext,
                        "get_flight_state_manager": lambda: flight,
                        "RunTick": paused_tick,
                        "replay_input_identity": lambda *a: ("inputs",),
                    }
                    ns = functions(
                        root,
                        "app/simulation/run_service.py",
                        ["collect"],
                        env,
                        cls="SimulationRunService",
                    )
                    probe.configure(role, "offline")
                    with modules(
                        **{
                            "app.core.metrics.prometheus_metrics": {
                                "FRAME_STORE": store
                            },
                            "app.core.metrics.frame_builder": {
                                "coordinator_identity": lambda x: "source"
                            },
                            "app.core.metrics.metric_updater": {
                                "clear_independent_dish_metrics": lambda: effects.append(
                                    "clear.independent"
                                )
                            },
                            "app.core.metrics": {
                                "clear_telemetry_metrics": lambda: effects.append(
                                    "clear"
                                )
                            },
                        }
                    ), probe.operation("tick", "tick"):
                        try:
                            result = ns["collect"](self_obj, coordinator, publish)
                            result_name = "telemetry" if result is telemetry else "none"
                        except ValueError as error:
                            result_name = str(error)
                    outputs.append((result_name, effects, store.read().status))
                    events = probe.drain()
                    if patched:
                        commits = [e for e in events if e["phase"] == "replay.commit"]
                        self.assertEqual(
                            len(commits), int(case in ("advance", "commit_error"))
                        )
                        if commits:
                            self.assertEqual(
                                commits[0]["outcome"],
                                "error" if case == "commit_error" else "ok",
                            )
                        contract.validate_stream(events)
                    if case == "advance":
                        self.assertLess(
                            effects.index("inplace" if role == "A" else "prepare"),
                            effects.index("commit"),
                        )
                        if role == "C":
                            self.assertLess(
                                effects.index("commit"),
                                effects.index("post_commit_publish"),
                            )
                self.assertEqual(outputs[0], outputs[1], (role, case))

    def test_a_real_inplace_metrics_and_caught_optional_errors(self):
        for case in ("normal", "disconnected", "exception"):
            outputs = []
            for patched in (False, True):
                root = roots("A")[patched]
                metric = module_at(root, "app/core/metrics/prometheus_metrics.py")
                mode = NS(value="estimated")
                phase = NS(value="pre_departure")
                flight = NS(
                    reset_detection=lambda: None,
                    get_status=lambda: NS(
                        phase=phase,
                        eta_mode=mode,
                        departure_time=None,
                        arrival_time=None,
                    ),
                )
                telemetry = NS(
                    position=NS(
                        latitude=1.0,
                        longitude=2.0,
                        altitude=300.0,
                        speed=0.0,
                        heading=90.0,
                        observed_at=None,
                        speed_observed_at=None,
                    ),
                    network=NS(
                        latency_ms=5.0,
                        throughput_down_mbps=10.0,
                        throughput_up_mbps=3.0,
                        packet_loss_percent=0.0,
                    ),
                    obstruction=NS(obstruction_percent=0.0),
                    environmental=NS(signal_quality_percent=99.0, uptime_seconds=60.0),
                    metric_availability=NS(
                        latency_ms=True,
                        throughput_down_mbps=True,
                        throughput_up_mbps=True,
                        packet_loss_percent=True,
                        obstruction_percent=True,
                    ),
                )
                if case == "exception":
                    telemetry.network = None
                env = {
                    **vars(metric),
                    "math": math,
                    "datetime": datetime,
                    "timezone": timezone,
                    "position_observation": lambda *a: (None, "unknown"),
                    "speed_is_fresh": lambda *a: False,
                    "logger": Log(),
                }
                ns = functions(
                    root,
                    "app/core/metrics/metric_updater.py",
                    ["update_metrics_from_telemetry"],
                    env,
                )
                probe.configure("A", "offline")
                with modules(
                    **{
                        "app.services.flight_state": {
                            "get_flight_state_manager": lambda: flight
                        },
                        "app.core.labels": {
                            "get_mode_label": lambda c: "simulation",
                            "get_telemetry_status_label": lambda t: "normal",
                        },
                        "app.core.eta_service": {
                            "update_eta_metrics": lambda *a, **kw: {}
                        },
                        "app.models.flight_status": {"ETAMode": NS(ESTIMATED=mode)},
                    }
                ):
                    try:
                        result = ns["update_metrics_from_telemetry"](
                            None if case == "disconnected" else telemetry
                        )
                        value = result
                    except AttributeError as e:
                        value = type(e).__name__
                if case == "normal":
                    self.assertIsNone(value)
                samples = [
                    (s.name, tuple(sorted(s.labels.items())), s.value)
                    for f in metric.REGISTRY.collect()
                    for s in f.samples
                    if not s.name.endswith("_created")
                ]
                outputs.append((value, samples, metric._current_position.copy()))
                events = probe.drain()
                if patched:
                    self.assertEqual(
                        [e["phase"] for e in events],
                        ["metrics.inplace.begin", "metrics.inplace.end"],
                    )
                    self.assertEqual(
                        events[-1]["outcome"], "error" if case == "exception" else "ok"
                    )
                    contract.validate_stream(events)
            self.assertEqual(outputs[0], outputs[1], case)


class ProducerLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_error_and_repeated_cancellation_keep_worker_owned(self):
        for role in ("A", "C"):
            for case in ("normal", "error", "double_cancel"):
                outcomes = []
                for patched in (False, True):
                    root = roots(role)[patched]
                    started, release, finished = (
                        threading.Event(),
                        threading.Event(),
                        threading.Event(),
                    )
                    sleeping = asyncio.Event()
                    effects = []

                    async def sleep(delay):
                        effects.append(("sleep", delay))
                        sleeping.set()
                        await asyncio.Event().wait()

                    facade = NS(
                        **{
                            name: getattr(asyncio, name)
                            for name in (
                                "create_task",
                                "to_thread",
                                "shield",
                                "gather",
                                "CancelledError",
                                "get_running_loop",
                            )
                        },
                        sleep=sleep
                    )

                    def tick(*a):
                        effects.append("worker.start")
                        started.set()
                        try:
                            if not release.wait(5):
                                raise TimeoutError("barrier")
                            if case == "error":
                                raise ValueError("worker")
                            return 1
                        finally:
                            effects.append("worker.end")
                            finished.set()

                    ns = functions(
                        root,
                        "main.py",
                        ["_background_update_loop"],
                        {
                            "asyncio": facade,
                            "os": os,
                            "logger": Log(),
                            "_background_update_tick": tick,
                            "app": NS(state=NS()),
                            "_simulation_config": NS(update_interval_seconds=0.1),
                            "_background_updates_enabled": True,
                        },
                    )
                    probe.configure(role, "offline")
                    with modules(
                        **{
                            "app.core.metrics": {
                                "simulation_errors_total": NS(
                                    inc=lambda: effects.append("error.counter")
                                )
                            }
                        }
                    ):
                        task = asyncio.create_task(ns["_background_update_loop"]())
                        try:
                            while not started.is_set():
                                await asyncio.sleep(0)
                            if case == "double_cancel":
                                task.cancel()
                                await asyncio.sleep(0)
                                task.cancel()
                                await asyncio.sleep(0)
                                self.assertFalse(task.done())
                                self.assertFalse(finished.is_set())
                            release.set()
                            if case != "double_cancel":
                                await asyncio.wait_for(sleeping.wait(), 5)
                            else:
                                self.assertTrue(finished.wait(5))
                            task.cancel()
                            result = (
                                await asyncio.gather(task, return_exceptions=True)
                            )[0]
                            outcomes.append((type(result).__name__, effects))
                        finally:
                            release.set()
                            task.cancel()
                            await asyncio.gather(task, return_exceptions=True)
                    events = probe.drain()
                    if patched:
                        self.assertEqual(
                            [e["phase"] for e in events],
                            [
                                "producer.dispatch",
                                "producer.start",
                                "producer.end",
                                "producer.returned",
                            ],
                        )
                        self.assertEqual(
                            events[-1]["outcome"],
                            (
                                "cancelled"
                                if case == "double_cancel"
                                else "error" if case == "error" else "ok"
                            ),
                        )
                        contract.validate_stream(events)
                self.assertEqual(outcomes[0], outcomes[1], (role, case))
