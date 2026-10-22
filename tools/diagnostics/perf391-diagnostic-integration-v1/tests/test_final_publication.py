"""Real C FrameStore publication/CAS; A never obtains these semantics."""

import unittest

from backend_support import functions, module_at, modules, probe, roots

import contract


class PublicationTests(unittest.TestCase):
    def exercise(self, patched):
        root = roots("C")[patched]
        frames = module_at(root, "app/core/metrics/frames.py")
        store = frames.FrameStore((frames.GaugeDefinition("g", "fixture"),))
        probe.configure("C", "offline")
        with probe.operation("tick", "tick"):
            expected = store.read()
            frame = frames.GaugeFrame(
                frames.FrameIdentity(
                    mode="live", observation_id="fixed", observation_timestamp=100.0
                ),
                ((((), 4.0),),),
                101.0,
            )
            self.assertTrue(store.publish(expected, frame))
            ready = store.read()
            self.assertFalse(store.publish(expected, frame))
            self.assertIs(store.read(), ready)
            self.assertFalse(store.fail(expected, "stale failure"))
            self.assertTrue(store.fail(ready, "failure"))
            pending = store.invalidate("input changed")
            self.assertEqual(pending.input_revision, 1)
            with self.assertRaises(ValueError):
                store.publish(pending, frame)
            with self.assertRaises(ValueError):
                store.publish(
                    pending,
                    frames.GaugeFrame(frames.FrameIdentity(input_revision=1), (), 1),
                )
        return (
            store.read().status,
            store.read().input_revision,
            store.read().frame.families,
        ), probe.drain()

    def test_stale_cas_schema_failure_and_nonready_swaps(self):
        control, _ = self.exercise(False)
        actual, events = self.exercise(True)
        self.assertEqual(actual, control)
        self.assertEqual(
            [e["outcome"] for e in events if e["phase"] == "publication.result"],
            ["ok", "cas_lost", "error", "error"],
        )
        self.assertEqual(
            len([e for e in events if e["phase"] == "producer.published"]), 1
        )
        self.assertEqual(
            [
                e["identity"]["publication_kind"]
                for e in events
                if e["phase"] == "publication.swap"
            ],
            ["ready", "fail", "invalidate"],
        )
        contract.validate_stream(events)

    def test_sink_failure_preserves_cas(self):
        with probe.faults():
            actual, _ = self.exercise(True)
        expected, _ = self.exercise(False)
        self.assertEqual(actual, expected)

    def test_final_predicate_exactly_once_and_captured_head_survives(self):
        for case in (
            "accepted",
            "rejected",
            "predicate_error",
            "preparation_error",
            "stale",
        ):
            outputs = []
            recorded = []
            for patched in (False, True):
                root = roots("C")[patched]
                frames = module_at(root, "app/core/metrics/frames.py")
                store = frames.FrameStore((frames.GaugeDefinition("g", "fixture"),))
                initial = store.read()
                frame = frames.GaugeFrame(
                    frames.FrameIdentity(mode="live", observation_id="fixed"),
                    ((((), 9.0),),),
                    100.0,
                )
                calls = []

                def prepare(*args, **kwargs):
                    calls.append("prepare")
                    captured = store.invalidate("during capture")
                    frame1 = frames.GaugeFrame(
                        frames.FrameIdentity(mode="live", input_revision=1),
                        frame.families,
                        100.0,
                    )
                    kwargs["_captured_head"](captured)
                    if case == "preparation_error":
                        raise ValueError("prepare")
                    if case == "stale":
                        store.invalidate("newer source")
                    return frame1

                def validate(candidate):
                    calls.append("final")
                    if case == "predicate_error":
                        raise ValueError("predicate")
                    return case != "rejected"

                namespace = functions(
                    root,
                    "app/core/metrics/metric_updater.py",
                    ["_update_metrics_from_telemetry_admitted"],
                    {
                        "_prepare_metrics_from_telemetry_admitted": prepare,
                        "logger": __import__("test_producer_integration").Log(),
                    },
                )
                probe.configure("C", "offline")
                with modules(
                    **{"app.core.metrics.prometheus_metrics": {"FRAME_STORE": store}}
                ), probe.operation("tick", "tick"):
                    namespace["_update_metrics_from_telemetry_admitted"](
                        object(), final_validation=validate
                    )
                head = store.read()
                outputs.append(
                    (
                        calls,
                        head.status,
                        head.reason,
                        head.input_revision,
                        head.frame.families if head.frame else None,
                    )
                )
                recorded.append(probe.drain())
                self.assertIsNot(head, initial)
            self.assertEqual(outputs[0], outputs[1], case)
            if case != "preparation_error":
                ends = [e for e in recorded[1] if e["phase"] == "source.final.end"]
                self.assertEqual(len(ends), 1)
                self.assertEqual(
                    ends[0]["outcome"],
                    {
                        "accepted": "ok",
                        "rejected": "rejected",
                        "predicate_error": "error",
                        "stale": "ok",
                    }[case],
                )
            self.assertEqual(
                len([e for e in recorded[1] if e["phase"] == "producer.published"]),
                int(case == "accepted"),
            )
            contract.validate_stream(recorded[1])

    def test_clear_and_service_swaps_never_claim_new_acquisition(self):
        import contextlib
        import math
        from datetime import datetime, timezone

        for case in ("clear", "service", "service_error"):
            outputs = []
            for patched in (False, True):
                root = roots("C")[patched]
                frames = module_at(root, "app/core/metrics/frames.py")
                schema = (
                    frames.GaugeDefinition(
                        "starlink_network_latency_ms_current", "fixture"
                    ),
                )
                store = frames.FrameStore(schema)
                effects = []
                frame = frames.GaugeFrame(
                    frames.FrameIdentity(
                        mode="live", observation_id="fixed", observation_timestamp=100.0
                    ),
                    ((((), 7.0),),),
                    100.0,
                )
                store.publish(store.read(), frame)

                def inputs(expected, **kwargs):
                    effects.append("inputs")
                    return expected

                def unavailable(expected):
                    effects.append("prepare")
                    if case == "service_error":
                        raise ValueError("optional")
                    return frames.GaugeFrame(
                        frames.FrameIdentity(
                            mode="simulation", input_revision=expected.input_revision
                        ),
                        ((((), math.nan),),),
                        100.0,
                    )

                admission = module_at(root, "app/mission/input_admission.py")
                ns = functions(
                    root,
                    "app/core/metrics/metric_updater.py",
                    ["clear_telemetry_metrics", "set_service_info"],
                    {
                        "model_input_write": admission.model_input_write,
                        "clear_independent_dish_metrics": lambda: effects.append(
                            "independent.clear"
                        ),
                        "math": math,
                        "datetime": datetime,
                        "UTC": timezone.utc,
                    },
                )
                probe.configure("C", "offline")
                with modules(
                    **{
                        "app.core.metrics.frame_builder": {
                            "FrameInputs": inputs,
                            "prepare_unavailable_frame": unavailable,
                        },
                        "app.core.metrics.frames": vars(frames),
                        "app.core.metrics.prometheus_metrics": {
                            "FRAME_STORE": store,
                            "COUPLED_SCHEMA": schema,
                        },
                        "app.mission.storage": {
                            "get_active_leg_lock": contextlib.nullcontext
                        },
                    }
                ), probe.operation("tick", "tick"):
                    try:
                        result = (
                            ns["clear_telemetry_metrics"]()
                            if case == "clear"
                            else ns["set_service_info"]("1", "simulation")
                        )
                    except ValueError as error:
                        result = type(error).__name__
                state = store.read()
                outputs.append(
                    (
                        result,
                        effects,
                        state.status,
                        state.reason,
                        str(state.frame.families),
                        state.frame.identity.observation_id,
                    )
                )
                events = probe.drain()
                if patched:
                    self.assertNotIn("producer.published", [e["phase"] for e in events])
                    kinds = [
                        e["identity"]["publication_kind"]
                        for e in events
                        if e["phase"] == "publication.swap"
                    ]
                    self.assertEqual(
                        kinds,
                        (
                            ["unavailable"]
                            if case == "clear"
                            else (
                                ["invalidate", "fail"]
                                if case == "service_error"
                                else ["invalidate", "service"]
                            )
                        ),
                    )
                    contract.validate_stream(events)
            self.assertEqual(outputs[0], outputs[1], case)
