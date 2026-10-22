"""Stage 3A source identity, protected-file parity and identical A/C hooks."""

import json
import tempfile
import unittest
from pathlib import Path
import build
from verify_frontend import verify

PACKAGE = Path(__file__).resolve().parents[1]


class FrontendGuards(unittest.TestCase):
    def test_exact_derivatives_and_reviewed_identical_frontend(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage3a-guard-") as temp:
            report = verify(PACKAGE.parents[2], Path(temp) / "export")
            self.assertEqual(
                report["roles"]["A"]["frontend_patch_sha256"],
                report["roles"]["C"]["frontend_patch_sha256"],
            )
            self.assertEqual(
                report["roles"]["A"]["frontend_tree_sha256"],
                report["roles"]["C"]["frontend_tree_sha256"],
            )
            self.assertFalse(report["image_built"])
            self.assertEqual(len(report["roles"]["A"]["frontend_files"]), 3)

    def test_stage3a_patch_cannot_apply_without_exact_stage2(self):
        with tempfile.TemporaryDirectory(prefix="perf391-stage3a-wrong-base-") as temp:
            root = Path(temp) / "A"
            build.export_source(PACKAGE.parents[2], "A", build.PINS["A"], root)
            spec = json.loads((PACKAGE / "patches/frontend/A.json").read_text())
            with self.assertRaisesRegex(build.GuardError, "unexpected source tree"):
                build.apply_patch(
                    root, (PACKAGE / "patches/frontend/A.patch").read_bytes(), spec
                )
