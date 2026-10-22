"""Existing post-commit and derived predicates retain every read/short circuit."""

import contextlib
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from backend_support import functions, module_at, modules, probe, roots
from test_producer_integration import Log

import contract


class AuthorityTests(unittest.TestCase):
    def test_complete_post_commit_predicate_and_error_paths(self):
        cases = (
            "accepted",
            "no_frame",
            "plan",
            "frame",
            "runtime",
            "revision",
            "run_missing",
            "run",
            "mission_time",
            "config",
            "telemetry",
            "timestamp",
            "inputs",
            "coordinator",
            "predicate_error",
        )
        for case in cases:
            outputs = []
            for patched in (False, True):
                root = roots("C")[patched]
                frames = module_at(root, "app/core/metrics/frames.py")
                store = frames.FrameStore((frames.GaugeDefinition("g", "fixture"),))
                head = store.read()
                calls = []
                plan = object()
                replay = object()
                stamp = datetime.fromtimestamp(100, timezone.utc)
                telemetry = NS(timestamp=stamp)
                run = NS(run_id="run", simulation_time=stamp)
                status = NS(runtime_id="runtime", revision=1, run=run)
                tick = NS(plan=plan, frame=replay)

                def selected():
                    calls.append("selected_plan")
                    if case == "predicate_error":
                        raise OSError("source reader")
                    return object() if case == "plan" else plan

                runtime = NS(
                    selected_plan=selected,
                    frame=lambda: (
                        calls.append("runtime.frame"),
                        object() if case == "frame" else replay,
                    )[1],
                )
                config = NS(
                    model_dump_json=lambda: (
                        calls.append("config"),
                        "changed" if case == "config" else "config",
                    )[1]
                )
                coordinator = NS(
                    get_config=lambda: config,
                    get_current_telemetry=lambda: (
                        calls.append("telemetry"),
                        object() if case == "telemetry" else telemetry,
                    )[1],
                )
                source = frames.FrameIdentity(
                    mode="replay",
                    coordinator_id="other" if case == "coordinator" else "source",
                    observation_timestamp=101.0 if case == "timestamp" else 100.0,
                    replay_runtime_id="other" if case == "runtime" else "runtime",
                    replay_revision="2" if case == "revision" else "1",
                    replay_run_id="other" if case == "run" else "run",
                    replay_mission_time=101.0 if case == "mission_time" else 100.0,
                )
                frame = frames.GaugeFrame(source, ((((), 7.0),),), 100.0)
                if case == "run_missing":
                    status.run = None
                obj = NS(
                    runtime=runtime, status=lambda: (calls.append("status"), status)[1]
                )
                ns = functions(
                    root,
                    "app/simulation/run_service.py",
                    ["publish_committed_metrics"],
                    {
                        "replay_input_identity": lambda *a: (
                            calls.append("inputs"),
                            ("changed",) if case == "inputs" else ("inputs",),
                        )[1],
                        "logger": Log(),
                    },
                    cls="SimulationRunService",
                )
                probe.configure("C", "offline")
                with modules(
                    **{
                        "app.core.metrics.prometheus_metrics": {"FRAME_STORE": store},
                        "app.core.metrics.frame_builder": {
                            "coordinator_identity": lambda c: (
                                calls.append("coordinator"),
                                "source",
                            )[1]
                        },
                    }
                ), probe.operation("replay", "replay"):
                    result = ns["publish_committed_metrics"](
                        obj,
                        head,
                        None if case == "no_frame" else frame,
                        tick,
                        coordinator,
                        ("source", "config"),
                        telemetry,
                        ("inputs",),
                    )
                outputs.append(
                    (
                        result,
                        calls,
                        store.read().status,
                        store.read().reason,
                        store.read().frame.families if store.read().frame else None,
                    )
                )
                events = probe.drain()
                if patched:
                    final = [e for e in events if e["phase"] == "source.final.end"]
                    self.assertEqual(len(final), int(case != "no_frame"))
                    if final:
                        self.assertEqual(
                            final[0]["outcome"],
                            (
                                "ok"
                                if case == "accepted"
                                else (
                                    "error" if case == "predicate_error" else "rejected"
                                )
                            ),
                        )
                    self.assertEqual(
                        sum(e["phase"] == "producer.published" for e in events),
                        int(case == "accepted"),
                    )
                    contract.validate_stream(events)
            self.assertEqual(outputs[0], outputs[1], case)

    def test_derived_same_frame_is_not_cas_or_acquisition(self):
        for case in ("unchanged", "changed", "rejected", "error"):
            outputs = []
            for patched in (False, True):
                root = roots("C")[patched]
                frames = module_at(root, "app/core/metrics/frames.py")
                store = frames.FrameStore((frames.GaugeDefinition("g", "fixture"),))
                calls = []
                stamp = datetime.fromtimestamp(100, timezone.utc)
                telemetry = NS(timestamp=stamp)
                identity = frames.FrameIdentity(
                    mode="simulation",
                    coordinator_id="source",
                    observation_id="obs",
                    route_id="route",
                    observation_timestamp=100.0,
                )
                previous = frames.GaugeFrame(identity, ((((), 7.0),),), 100.0)
                store.publish(store.read(), previous)
                coordinator = NS(
                    _last_valid_telemetry=telemetry,
                    route_progress_snapshot=lambda: (
                        calls.append("progress"),
                        (0.0, 0),
                    )[1],
                )
                config = NS(
                    mode="simulation",
                    model_dump_json=lambda: (calls.append("config"), "config")[1],
                )
                route = object()
                routes = NS(get_active_route=lambda: (calls.append("route"), route)[1])
                manager = NS(list_pois=lambda: (calls.append("pois"), [])[1])

                def sources():
                    calls.append("sources")
                    if calls.count("sources") == 2 and case == "error":
                        raise ValueError("reader")
                    return coordinator, config, routes, manager, None

                def prepare(inputs, *, admit_observation):
                    calls.append(("prepare", admit_observation))
                    return (
                        previous
                        if case == "unchanged"
                        else frames.GaugeFrame(identity, ((((), 8.0),),), 100.0)
                    )

                builder = NS(
                    coordinator_identity=lambda c: (calls.append("identity"), "source")[
                        1
                    ],
                    model_identity=lambda v: "obs" if v is telemetry else "route",
                    FrameInputs=lambda *a, **kw: NS(),
                    prepare_frame=prepare,
                )
                ns = functions(
                    root,
                    "app/core/metrics/refresh_inputs.py",
                    ["refresh_current_metrics"],
                    {
                        "datetime": datetime,
                        "UTC": timezone.utc,
                        "FRAME_STORE": store,
                        "get_active_leg_lock": contextlib.nullcontext,
                        "frame_builder": builder,
                        "route_source_identity": lambda r: (
                            calls.append("route.key"),
                            "route-key",
                        )[1],
                        "get_flight_state_manager": lambda: NS(
                            get_status=lambda **kw: NS()
                        ),
                        "frame_inputs_are_current": lambda *a: (
                            calls.append("final.inputs"),
                            case != "rejected",
                        )[1],
                        "logger": Log(),
                    },
                )
                probe.configure("C", "offline")
                with modules(
                    **{
                        "app.services.position_freshness": {
                            "observation_time": lambda *a: (stamp, "fresh")
                        }
                    }
                ), probe.operation("tick", "tick"):
                    result = ns["refresh_current_metrics"](
                        sources, now=datetime.fromtimestamp(101, timezone.utc)
                    )
                outputs.append(
                    (
                        result,
                        calls,
                        store.read().status,
                        store.read().reason,
                        store.read().frame.families,
                    )
                )
                events = probe.drain()
                if patched:
                    self.assertNotIn("producer.published", [e["phase"] for e in events])
                    self.assertNotIn("producer.collected", [e["phase"] for e in events])
                    finals = [e for e in events if e["phase"] == "source.final.end"]
                    self.assertEqual(len(finals), int(case != "error"))
                    if case == "unchanged":
                        self.assertFalse(
                            any(e["phase"] == "publication.attempt" for e in events)
                        )
                        self.assertEqual(
                            [
                                e["outcome"]
                                for e in events
                                if e["phase"] == "publication.result"
                            ],
                            ["unchanged"],
                        )
                    self.assertEqual(
                        {e["operation_type"] for e in events}, {"derived_refresh"}
                    )
                    self.assertEqual({e["parent_op_id"] for e in events}, {"tick"})
                    contract.validate_stream(events)
            self.assertEqual(outputs[0], outputs[1], case)
