import json
import tempfile
import unittest
from pathlib import Path

from perf391_network_evidence.cli import main, read_rows


class CliTests(unittest.TestCase):
    def test_fixture_replay_machine_and_human_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "results.json"
            self.assertEqual(main(["fixtures", "--output", str(output)]), 0)
            results = json.loads(output.read_text())
            self.assertEqual(results["passed"], 16)
            case = results["cases"][0]["analysis"]
            from perf391_network_evidence.analyze import human

            self.assertIn("not evaluated", human(case))

    def test_collection_duration_hard_cap(self):
        with self.assertRaises(SystemExit):
            main(
                [
                    "host",
                    "--output",
                    "unused",
                    "--run-id",
                    "x",
                    "--duration",
                    "3660",
                    "--diagnostic-lane",
                ]
            )

    def test_artifact_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "events.jsonl"
            p.write_text(
                json.dumps(
                    {"data": {"artifact": {"state": "available", "path": "../outside"}}}
                )
                + "\n"
            )
            with self.assertRaises(ValueError):
                read_rows([p])

    def test_signal_cleanup_with_fictional_resource_sampler(self):
        import os
        import signal
        import subprocess
        import sys
        import time

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "owned"
            script = (
                "from perf391_network_evidence import cli; cli.sample_resources=lambda **kw: {'files':{}}; cli.main(['host','--output',"
                + repr(str(root))
                + ",'--run-id','fictional-signal-test','--duration','180','--diagnostic-lane'])"
            )
            child = subprocess.Popen(
                [sys.executable, "-c", script],
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            try:
                deadline = time.monotonic() + 3
                while (
                    not (root / "owner.json").exists()
                    and child.poll() is None
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
                self.assertTrue((root / "owner.json").exists())
                child.send_signal(signal.SIGTERM)
                self.assertEqual(child.wait(timeout=3), 0)
                self.assertTrue(
                    json.loads((root / "cleanup.json").read_text())["closed"]
                )
                rows = read_rows([root / "events.jsonl"])
                self.assertEqual(rows[-1]["kind"], "summary")
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)
