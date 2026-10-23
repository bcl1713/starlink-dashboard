import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from perf391_network_evidence.analyze import analyze
from perf391_network_evidence.model import event, validate
from perf391_network_evidence.record import Recorder


class CoreTests(unittest.TestCase):
    def test_schema_compatibility_and_intentional_missing(self):
        row = event(
            "coverage",
            {
                "boundary": "producer.returned",
                "available": False,
                "reason": "not instrumented",
            },
            mono_ns=1,
        )
        validate(row)
        for key, value in [("version", 2), ("unknown", True), ("mono_ns", "-1")]:
            with self.assertRaises(ValueError):
                validate(dict(row, **{key: value}))
        bad = copy.deepcopy(row)
        bad["data"]["reason"] = None
        with self.assertRaises(ValueError):
            validate(bad)
        with self.assertRaises(ValueError):
            validate(
                event(
                    "scrape",
                    {
                        "series": "x",
                        "timestamp": 1,
                        "value": float("nan"),
                        "state": "finite",
                        "segment": "measured",
                    },
                    mono_ns=2,
                )
            )

    def test_bounded_recorder_drop_summary_artifacts_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with Recorder(
                root,
                max_events=2,
                max_bytes=8192,
                max_event_bytes=2048,
                max_disk_bytes=20000,
                max_body_bytes=10,
            ) as recorder:
                recorder.emit(
                    "coverage",
                    {"boundary": "paint", "available": False, "reason": "absent"},
                )
                recorder.emit(
                    "coverage",
                    {"boundary": "paint", "available": False, "reason": "absent"},
                )
                self.assertFalse(
                    recorder.emit(
                        "coverage",
                        {"boundary": "paint", "available": False, "reason": "overflow"},
                    )
                )
                self.assertEqual(
                    recorder.artifact(b"01234567890")["state"], "unavailable"
                )
                body = recorder.artifact(b"abc")
                self.assertEqual((root / body["path"]).read_bytes(), b"abc")
                recorder.drain()
                recorder.emit(
                    "coverage",
                    {"boundary": "paint", "available": False, "reason": "absent"},
                )
            rows = [
                json.loads(x) for x in (root / "events.jsonl").read_text().splitlines()
            ]
            self.assertEqual(rows[-1]["kind"], "summary")
            self.assertEqual(rows[-1]["data"]["dropped_events"], 1)
            self.assertEqual(rows[-1]["data"]["dropped_bodies"], 1)
            self.assertTrue(recorder.closed)
            self.assertLessEqual(
                sum(p.stat().st_size for p in root.rglob("*") if p.is_file()), 20000
            )
            self.assertEqual(len({r["seq"] for r in rows}), len(rows))

    def test_ids_clocks_missing_and_duplicate_boundaries(self):
        def b(name, ns, clock="a", op="r1"):
            return event(
                "boundary",
                {"name": name},
                mono_ns=ns,
                clock_id=clock,
                op_id=op,
                stream_id=clock,
                seq=ns,
            )

        rows = [
            b("worker.dispatch", 100),
            b("worker.start", 200),
            b("worker.end", 300),
            b("worker.returned", 900),
            b("observer.send", 1, "client"),
            b("observer.received", 50, "client"),
        ]
        result = analyze(rows)
        joined = result["operations"]["r1"]
        self.assertEqual(joined["worker_queue"]["value_ns"], 100)
        self.assertEqual(joined["worker_completion"]["value_ns"], 600)
        self.assertEqual(joined["observer_http"]["value_ns"], 49)
        self.assertIsNone(joined["producer_publication"]["value_ns"])
        rows.append(b("worker.returned", 950))
        self.assertIsNone(
            analyze(rows)["operations"]["r1"]["worker_completion"]["value_ns"]
        )
        rows = [b("worker.dispatch", 100), b("worker.start", 200, "restart")]
        self.assertEqual(
            analyze(rows)["operations"]["r1"]["worker_queue"]["reason"],
            "clock_domain_mismatch",
        )

    def test_clock_step_no_cross_origin_subtraction(self):
        rows = [
            event("anchor", {"utc_ns": "1000000"}, mono_ns=100, seq=1),
            event("anchor", {"utc_ns": "5000000"}, mono_ns=200, seq=2),
        ]
        self.assertEqual(
            analyze(rows)["clock_adjustments"][0]["offset_change_ns"], 3999900
        )

    def test_fixture_classifications_and_hashes(self):
        root = Path(__file__).resolve().parents[1] / "fixtures"
        manifest = json.loads((root / "SHA256SUMS.json").read_text())
        for name, digest in manifest.items():
            self.assertEqual(
                hashlib.sha256((root / name).read_bytes()).hexdigest(), digest
            )
        for case in json.loads((root / "cases.json").read_text()):
            with self.subTest(case=case["name"]):
                result = analyze(case["events"])
                self.assertTrue(
                    set(case.get("expected", []))
                    <= {r["classification"] for r in result["charts"]},
                    result,
                )
                for metric, expected in case.get("durations", {}).items():
                    self.assertEqual(
                        result["operations"]["r1"][metric]["value_ns"], expected
                    )


if __name__ == "__main__":
    unittest.main()


class StorageLimitTests(unittest.TestCase):
    def test_byte_disk_limits_and_summary_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            with Recorder(
                tmp,
                max_events=50,
                max_bytes=2048,
                max_event_bytes=1024,
                max_disk_bytes=7000,
                max_body_bytes=64,
            ) as rec:
                rec.emit(
                    "coverage",
                    {"boundary": "large", "available": False, "reason": "x" * 2000},
                )
                for i in range(100):
                    rec.emit(
                        "coverage",
                        {"boundary": "x", "available": False, "reason": "fixture"},
                    )
                    rec.drain()
                self.assertGreater(rec.dropped_events, 0)
            root = Path(tmp)
            self.assertLessEqual(
                sum(p.stat().st_size for p in root.rglob("*") if p.is_file()), 7000
            )
            self.assertEqual(
                json.loads((root / "events.jsonl").read_text().splitlines()[-1])[
                    "kind"
                ],
                "summary",
            )
