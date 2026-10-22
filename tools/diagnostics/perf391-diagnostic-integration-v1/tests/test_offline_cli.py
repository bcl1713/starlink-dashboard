"""Offline CLI process proof; no application, service, browser or HTTP startup."""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from stage4_fixture import fixture

from owner import Owner


class OfflineImportTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_manifest_run_matches_its_evidence_and_child_is_reaped(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage4-cli-") as tmp:
            root = Path(tmp)
            rows = [json.loads(line) for line in fixture()["events.jsonl"].splitlines()]
            backend = root / "backend.jsonl"
            backend.write_text(
                "".join(
                    json.dumps(row) + "\n"
                    for row in rows
                    if row["emitter"] == "backend"
                )
            )
            stats = root / "stats.json"
            stats.write_text(
                json.dumps({"buffered": 0, "dropped": 0, "invalid": 0, "failures": 0})
            )
            owner = Owner(root / "test-owner", run="synthetic-test", sources={})
            with (root / "log").open("wb") as log:
                child = owner.spawn(
                    [
                        sys.executable,
                        "-B",
                        "run.py",
                        "integrate",
                        "--role",
                        "C",
                        "--backend",
                        str(backend),
                        "--stats",
                        str(stats),
                        "--output",
                        str(root / "import"),
                    ],
                    stdout=log,
                )
                try:
                    status = await asyncio.to_thread(child.wait, timeout=10)
                finally:
                    await owner.close()
            self.assertEqual(status, 0, (root / "log").read_text())
            manifest = json.loads((root / "import/manifest.json").read_text())
            self.assertEqual(manifest["run_id"], "synthetic-test")
            self.assertEqual(manifest["status"], "clean")
            self.assertIsNotNone(child.returncode)
