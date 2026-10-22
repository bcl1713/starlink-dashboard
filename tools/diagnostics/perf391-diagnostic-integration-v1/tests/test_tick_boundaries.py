"""Run the complete original tick with barriers in detached metric preparation.

Fixture managers expose fixed scalars and record every read. Moving a probe to a
new source read/check, or skipping the existing final predicate, changes outputs.
"""

import contextlib
import sqlite3
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from backend_support import functions, module_at, modules, probe, roots
from test_producer_integration import Log

import contract


class TickTests(unittest.TestCase):
    def execute(self, role, patched, case, fault=False):
        root = roots(role)[patched]
        frame_module = module_at(roots("C")[patched], "app/core/metrics/frames.py")
        store = frame_module.FrameStore((frame_module.GaugeDefinition("g", "fixture"),))
        calls = []
        observations = []

        class Model:
            def __init__(self, name):
                self.name = name
                self.rev = 0
                self.mode = (
                    "live" if case in ("mission", "post_event") else "simulation"
                )

            def model_dump_json(self):
                calls.append("config.read")
                return str(self.rev)

        config = Model("config")
        route = Model("route")
        mission = Model("mission")
        poi = Model("poi")
        routes = NS(
            active=route,
            get_active_route=lambda: (calls.append("route.read"), routes.active)[1],
            get_active_route_id=lambda: (calls.append("route.id"), "route-id")[1],
        )
        old = NS(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
        telemetry = (
            None
            if case == "disconnect"
            else (
                old
                if case == "retained"
                else NS(timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc))
            )
        )
        coordinator = NS(
            current=old,
            lifecycle="source-1",
            get_current_telemetry=lambda: (
                calls.append("telemetry.read"),
                coordinator.current,
            )[1],
            is_connected=lambda: False,
            route_progress_snapshot=lambda: (calls.append("progress"), (1.0, 1))[1],
        )

        def collect():
            calls.append("collect")
            if case == "collection_error":
                raise OSError("offline sensor")
            coordinator.current = telemetry
            return telemetry

        coordinator.update = collect
        status = NS(runtime_id="runtime", revision=1)
        service = NS(
            runtime=NS(selected_plan=lambda: None),
            status=lambda: (calls.append("runtime.read"), status)[1],
        )

        def record_live(t):
            calls.append("event.record")
            if case == "post_event":
                config.rev += 1

        runtime = NS(
            tick=lambda: calls.append("event.tick"),
            record_live=record_live,
            observe_live=lambda *a: calls.append("event.observe"),
            sync_legacy_phase=lambda *a: calls.append("event.sync"),
        )
        state = NS(simulation_run_service=service)
        if case in ("mission", "post_event"):
            state.flight_event_runtime = runtime

        def source_identity(value):
            calls.append("coordinator.identity")
            return value.lifecycle if value else "none"

        def mutate():
            if case == "coordinator":
                ns["_coordinator"] = NS(lifecycle="replacement")
            elif case == "config":
                config.rev += 1
            elif case == "route":
                routes.active = Model("replacement")
            elif case == "poi":
                poi.rev += 1
            elif case == "mission":
                mission.rev += 1
            elif case == "replay_revision":
                status.revision += 1
            elif case == "stale":
                store.invalidate("newer head")

        def prepare(*a, **kw):
            calls.append("prepare")
            expected = store.read()
            kw["_captured_head"](expected)
            frame = frame_module.GaugeFrame(
                frame_module.FrameIdentity(
                    mode="live",
                    observation_id="fixed",
                    observation_timestamp=100.0,
                    input_revision=expected.input_revision,
                ),
                ((((), 7.0),),),
                100.0,
            )
            observations.append(("account", 7))
            mutate()
            if case == "metric_error":
                raise ValueError("optional metric preparation")
            return frame

        admitted = (
            functions(
                root,
                "app/core/metrics/metric_updater.py",
                ["_update_metrics_from_telemetry_admitted"],
                {"_prepare_metrics_from_telemetry_admitted": prepare, "logger": Log()},
            )["_update_metrics_from_telemetry_admitted"]
            if role == "C"
            else None
        )

        def inplace(*a, **kw):
            calls.append("inplace")
            observations.append(("inplace", a[0] is not None))
            if case == "metric_error":
                raise ValueError("optional metric preparation")

        env = {
            "_coordinator": None if case == "no_coordinator" else coordinator,
            "_route_manager": routes,
            "_current_runtime_config": lambda: config,
            "SimulationConfig": Model,
            "should_automatically_refresh_ground_entry_point": lambda c: False,
            "app": NS(state=state),
            "_publish_pop_observation": lambda *a: calls.append("pop"),
            "_refresh_metrics_without_collection": lambda: calls.append("refresh"),
            "logger": Log(),
            "time": NS(time=lambda: 100.0),
            "sqlite3": sqlite3,
            "mission_storage": NS(
                load_mission_v2=lambda m: (
                    calls.append("mission.read"),
                    NS(model_dump_json=lambda: str(mission.rev)),
                )[1]
            ),
        }
        ns = functions(root, "main.py", ["_background_update_tick"], env)
        module_values = {
            "app.core.metrics.frames": vars(frame_module),
            "app.core.metrics.frame_builder": {"coordinator_identity": source_identity},
            "app.core.metrics.prometheus_metrics": {"FRAME_STORE": store},
            "app.core.metrics.source_admission": {
                "frame_inputs_are_current": lambda *a: (
                    calls.append("frame.inputs"),
                    poi.rev == 0,
                )[1],
                "route_source_identity": lambda r: (
                    calls.append("route.identity"),
                    r.name if r else None,
                )[1],
                "model_identity": lambda m: m.model_dump_json(),
            },
            "app.mission.storage": {"get_active_leg_lock": contextlib.nullcontext},
            "app.core.metrics": {
                "update_metrics_from_telemetry": inplace,
                "clear_telemetry_metrics": lambda **kw: calls.append("clear"),
                "starlink_metrics_generation_errors_total": NS(
                    inc=lambda: calls.append("metric.error")
                ),
                "starlink_metrics_last_update_timestamp_seconds": NS(
                    set=lambda v: calls.append("last_update")
                ),
                "starlink_metrics_scrape_duration_seconds": NS(
                    observe=lambda v: calls.append(("duration", v))
                ),
            },
            "app.core.metrics.metric_updater": {
                "_update_metrics_from_telemetry_admitted": admitted
            },
            "app.mission.active_context": {
                "resolve_active_mission_leg_context": lambda r: NS(
                    context=NS(
                        parent_mission_id="mission",
                        parent_mission=NS(model_dump_json=lambda: str(mission.rev)),
                        leg=NS(id="leg"),
                    )
                )
            },
            "app.services.flight_state": {"get_flight_state_manager": lambda: None},
        }
        probe.configure(role, "offline")
        with modules(**module_values), probe.operation("tick", "tick"), (
            probe.faults() if fault else contextlib.nullcontext()
        ):
            try:
                result = ns["_background_update_tick"](poi, 1.0, 0, 0)
            except OSError as error:
                result = (type(error).__name__, str(error))
        head = store.read()
        return (
            result,
            calls,
            observations,
            head.status,
            head.input_revision,
            head.frame.families if head.frame else None,
        ), probe.drain()

    def test_tick_branches_and_final_source_transitions(self):
        cases = (
            "normal",
            "retained",
            "disconnect",
            "no_coordinator",
            "collection_error",
            "metric_error",
            "post_event",
            "coordinator",
            "config",
            "route",
            "poi",
            "mission",
            "replay_revision",
            "stale",
        )
        for role in ("A", "C"):
            for case in cases:
                with self.subTest(role=role, case=case):
                    control, _ = self.execute(role, False, case)
                    actual, events = self.execute(role, True, case)
                    self.assertEqual(actual, control)
                    boundaries = [
                        e
                        for e in events
                        if e["phase"] in ("collection.enter", "collection.return")
                    ]
                    self.assertEqual(
                        [e["phase"] for e in boundaries],
                        (
                            []
                            if case == "no_coordinator"
                            else ["collection.enter", "collection.return"]
                        ),
                    )
                    collected = [
                        e for e in events if e["phase"] == "producer.collected"
                    ]
                    self.assertEqual(
                        len(collected),
                        int(case not in ("no_coordinator", "collection_error")),
                    )
                    if role == "C" and case in (
                        "coordinator",
                        "config",
                        "route",
                        "poi",
                        "mission",
                        "replay_revision",
                        "stale",
                    ):
                        self.assertNotIn(
                            "producer.published", [e["phase"] for e in events]
                        )
                        self.assertEqual(
                            actual[3], "pending" if case == "stale" else "failed"
                        )
                    contract.validate_stream(events)

    def test_sink_faults_preserve_tick_branches_and_outputs(self):
        for role in ("A", "C"):
            for case in (
                "normal",
                "retained",
                "disconnect",
                "collection_error",
                "metric_error",
                "config",
                "stale",
            ):
                control, _ = self.execute(role, False, case)
                actual, _ = self.execute(role, True, case, fault=True)
                self.assertEqual(actual, control, (role, case))
