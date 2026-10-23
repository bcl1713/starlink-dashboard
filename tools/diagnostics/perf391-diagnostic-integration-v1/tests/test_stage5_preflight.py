"""Offline release verifier must reject altered/missing/symlinked artifacts."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class Stage5PreflightTests(unittest.TestCase):
    def test_offline_preflight_accepts_exact_hashes_and_rejects_bad_artifacts(self):
        package = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="perf391-stage5-preflight-") as tmp:
            root = Path(tmp)
            shutil.copy2(package / "forge-preflight.sh", root)
            (root / "evidence/stage5").mkdir(parents=True)
            artifact = root / "fixture.bin"
            artifact.write_bytes(b"fixture")
            manifest = {
                "schema": "perf391-stage5-release-v1",
                "files": {"fixture.bin": hashlib.sha256(b"fixture").hexdigest()},
                "qualification": "offline_only",
                "source_files": ["fixture.bin", "forge-preflight.sh"],
            }
            manifest["files"]["forge-preflight.sh"] = hashlib.sha256(
                (root / "forge-preflight.sh").read_bytes()
            ).hexdigest()
            (root / "evidence/stage5/release-manifest.json").write_text(
                json.dumps(manifest)
            )

            def run():
                return subprocess.run(
                    ["bash", str(root / "forge-preflight.sh"), "--offline"],
                    check=False,
                    capture_output=True,
                    timeout=10,
                )

            self.assertEqual(run().returncode, 0)
            extra = root / "unreviewed.py"
            extra.write_text("# unexpected source\n")
            self.assertNotEqual(run().returncode, 0)
            extra.unlink()
            artifact.write_bytes(b"changed")
            self.assertNotEqual(run().returncode, 0)
            artifact.unlink()
            self.assertNotEqual(run().returncode, 0)
            artifact.symlink_to(root / "forge-preflight.sh")
            self.assertNotEqual(run().returncode, 0)
