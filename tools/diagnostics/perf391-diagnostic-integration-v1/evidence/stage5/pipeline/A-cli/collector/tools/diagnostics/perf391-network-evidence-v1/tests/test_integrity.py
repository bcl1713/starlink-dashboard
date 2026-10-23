import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path

from perf391_network_evidence.adapters import diagnostic_worker
from perf391_network_evidence.analyze import analyze
from perf391_network_evidence.ingestion import stored_events
from perf391_network_evidence.model import event, validate
from perf391_network_evidence.record import Recorder


class IntegrityTests(unittest.TestCase):
    def test_bad_chart_lengths_and_scrape_state_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        rows = json.loads((root / "fixtures/cases.json").read_text())[0]["events"]
        chart = copy.deepcopy(rows[-1])
        chart["data"]["traces"]["observed"].pop()
        with self.assertRaises(ValueError):
            validate(chart)
        scrape = copy.deepcopy(rows[2])
        scrape["data"].update(state="finite", value=None)
        with self.assertRaises(ValueError):
            validate(scrape)

    def test_store_export_separates_nan_missing_family_and_failed_scrape(self):
        def matrix(name, values):
            return {"metric": {"__name__": name}, "values": values}

        data = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    matrix("up", [[100, "1"], [101, "1"], [102, "0"]]),
                    matrix("latency", [[100, "0"], [101, "NaN"]]),
                    matrix("scrape_duration_seconds", [[100, "0.01"]]),
                ],
            },
        }
        rows = stored_events(data, fields=["latency", "downlink"], run_id="stored")
        self.assertEqual(
            [r["data"]["state"] for r in rows if r["data"]["series"] == "latency"],
            ["finite", "nan", "failed"],
        )
        self.assertEqual(
            [r["data"]["state"] for r in rows if r["data"]["series"] == "downlink"],
            ["missing", "missing", "failed"],
        )
        self.assertIsNone(rows[-1]["data"]["scrape_duration_seconds"])

    def test_drop_or_absent_summary_never_claims_complete_evidence(self):
        result = analyze(
            [
                event(
                    "summary",
                    {
                        "dropped_events": 1,
                        "dropped_bodies": 0,
                        "written_bytes": 0,
                        "write_wall_ns": "0",
                        "reason": "fixture",
                    },
                )
            ]
        )
        self.assertIn("collection_loss", result["issues"])
        self.assertFalse(analyze([])["summary_present"])

    def test_worker_cancellation_drains_owned_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            with Recorder(tmp) as rec:

                async def run():
                    import threading

                    began = threading.Event()
                    finish = threading.Event()

                    def work():
                        began.set()
                        finish.wait(2)
                        return 42

                    task = asyncio.create_task(
                        diagnostic_worker(rec, "producer", "t1", work)
                    )
                    while not began.is_set():
                        await asyncio.sleep(0.001)
                    task.cancel()
                    finish.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

                asyncio.run(run())
            rows = [
                json.loads(x)
                for x in (Path(tmp) / "events.jsonl").read_text().splitlines()
            ]
            self.assertEqual(
                [r["data"]["name"] for r in rows if r["kind"] == "boundary"][-2:],
                ["producer.end", "producer.returned"],
            )

    def test_admission_fixture_and_unique_gap_dedup(self):
        cases = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/cases.json").read_text()
        )
        gate = next(c for c in cases if c["name"] == "repository_contention")
        result = analyze(gate["events"])
        self.assertEqual(
            result["admissions"][0]["wait"]["value_ns"], gate["admission_wait_ns"]
        )
        missing = copy.deepcopy(
            next(c for c in cases if c["name"] == "missing_scrape")["events"]
        )
        repeat = copy.deepcopy(missing)
        for row in repeat:
            row["seq"] += 100
            if row["kind"] in ("history", "chart"):
                row["data"].update(request_id="poll2", bundle_id="b2")
        self.assertEqual(analyze(missing + repeat)["unique_api_missing_slots"], 1)


if __name__ == "__main__":
    unittest.main()
