import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import contract  # noqa: E402


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.event = json.loads((PACKAGE / "fixtures/event.json").read_text())

    def test_valid_fixture_and_contract(self):
        contract.validate_event(self.event)
        contract.validate_stream(
            [self.event, {**self.event, "seq": 2, "mono_ns": "101"}]
        )
        self.assertEqual(
            contract.capability("A", "ready_frame_cas")["available"], False
        )
        self.assertEqual(contract.capability("C", "ready_frame_cas")["available"], True)
        self.assertFalse(contract.capability("C", "missing")["available"])

    def test_closed_event_and_bounded_identity(self):
        for key, value in [
            ("extra", True),
            ("phase", "invented"),
            ("outcome", "success"),
            ("op_id", "x" * 97),
            ("op_id", "nonascii☃"),
            ("mono_ns", 123),
            ("mono_ns", "-1"),
            ("version", 2),
            ("identity", {"invented": "x"}),
            ("identity", {"route_revision": "x" * 257}),
            ("identity", {"route_revision": {"nested": True}}),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(
                contract.ContractError
            ):
                contract.validate_event({**self.event, key: value})
        for key in self.event:
            event = self.event.copy()
            del event[key]
            with self.subTest(missing=key), self.assertRaises(contract.ContractError):
                contract.validate_event(event)

    def test_a_cas_and_browser_thread_unavailable(self):
        for changes in (
            {"role": "A", "phase": "producer.published"},
            {"role": "A", "identity": {"expected_head": "token"}},
            {"emitter": "browser"},
            {"thread_cpu_ns": "1", "tid": None},
            {"identity": {"observation_timestamp": None}, "unavailable": {}},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                contract.ContractError
            ):
                contract.validate_event({**self.event, **changes})
        event = {
            **self.event,
            "emitter": "browser",
            "tid": None,
            "thread_start_id": None,
            "thread_cpu_ns": None,
        }
        contract.validate_event(event)
        contract.validate_event(
            {
                **self.event,
                "identity": {"observation_timestamp": None},
                "unavailable": {"observation_timestamp": "not exposed"},
            }
        )

    def test_only_successful_ready_cas_publishes(self):
        for outcome, identity in [
            ("cas_lost", {"publication_kind": "ready", "cas_success": True}),
            ("ok", {"publication_kind": "failure", "cas_success": True}),
            ("ok", {"publication_kind": "ready", "cas_success": False}),
            ("ok", {}),
        ]:
            with self.subTest(outcome=outcome, identity=identity), self.assertRaises(
                contract.ContractError
            ):
                contract.validate_event(
                    {
                        **self.event,
                        "phase": "producer.published",
                        "outcome": outcome,
                        "identity": identity,
                    }
                )
        contract.validate_event(
            {
                **self.event,
                "phase": "producer.published",
                "identity": {"publication_kind": "ready", "cas_success": True},
            }
        )

    def test_sequence_gap_restart_and_clock_mismatch_visible(self):
        for second in (
            {"seq": 1},
            {"seq": 3},
            {"seq": 2, "process_uuid": "22222222-2222-4222-8222-222222222222"},
            {"seq": 2, "clock_id": "different"},
            {"seq": 2, "mono_ns": "99"},
        ):
            with self.subTest(second=second), self.assertRaises(contract.ContractError):
                contract.validate_stream([self.event, {**self.event, **second}])
        contract.validate_stream(
            [
                self.event,
                {
                    **self.event,
                    "stream_id": "restart",
                    "clock_id": "restart-clock",
                    "process_uuid": "22222222-2222-4222-8222-222222222222",
                },
            ]
        )

    def test_derived_refresh_cannot_publish(self):
        with self.assertRaises(contract.ContractError):
            contract.validate_event(
                {
                    **self.event,
                    "phase": "producer.published",
                    "operation_type": "derived_refresh",
                    "identity": {"publication_kind": "ready", "cas_success": True},
                }
            )

    def test_document_and_cross_stream_clock_reuse(self):
        first = {
            **self.event,
            "emitter": "browser",
            "tid": None,
            "thread_start_id": None,
            "thread_cpu_ns": None,
            "identity": {"document_id": "doc1"},
        }
        for second in (
            {**first, "seq": 2, "identity": {"document_id": "doc2"}},
            {**first, "stream_id": "navigation", "identity": {"document_id": "doc2"}},
            {
                **self.event,
                "stream_id": "restart",
                "process_uuid": "22222222-2222-4222-8222-222222222222",
            },
        ):
            with self.subTest(second=second), self.assertRaises(contract.ContractError):
                contract.validate_stream(
                    [first if second["emitter"] == "browser" else self.event, second]
                )
        contract.validate_stream(
            [
                first,
                {
                    **first,
                    "stream_id": "navigation",
                    "clock_id": "navigation-clock",
                    "identity": {"document_id": "doc2"},
                },
            ]
        )

    def test_contract_phase_outcome_and_capability_agreement(self):
        schema = json.loads((PACKAGE / "integration-event-schema.json").read_text())
        spec = json.loads((PACKAGE / "contract.json").read_text())
        self.assertEqual(schema["properties"]["phase"]["enum"], spec["phases"])
        self.assertEqual(schema["properties"]["outcome"]["enum"], spec["outcomes"])
        self.assertFalse(spec["runtime_authorized"])


if __name__ == "__main__":
    unittest.main()
