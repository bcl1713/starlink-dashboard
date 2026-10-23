"""Offline identity regressions; no browser or Docker execution."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from launcher import validate_receipt
from prepare import HERE, sha
from runtime_identity import verify_runtime_identity, verify_runtime_overlay

BUILT = HERE.with_name("perf391-built-images-v1")
PLAN_PATH = BUILT / "evidence/runtime-build-plan.json"
NODE_HASH = "81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90"


class NodeIdentityTests(unittest.TestCase):
    def test_correction_layer_rejects_uninventoried_or_changed_source(self):
        from correction import verify_correction
        from prepare import HERE

        manifest = json.loads(
            (HERE / "diagnostic-correction-overlay.json").read_bytes()
        )
        name = next(iter(manifest["source_files"]))
        manifest["source_files"][name]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source drift"):
            verify_correction(manifest)
        del manifest["source_files"][name]
        with self.assertRaisesRegex(ValueError, "source inventory"):
            verify_correction(manifest)

    def test_receipt_identity_pairs_fail_closed(self):
        plan = json.loads(PLAN_PATH.read_bytes())
        for role in ("A", "C"):
            receipt = json.loads((BUILT / f"evidence/built-{role}.json").read_bytes())
            validate_receipt(receipt, plan, sha(PLAN_PATH))
            for version, digest in [
                ("22.12.0", NODE_HASH),
                ("22.22.2", "0" * 64),
                ("22.23.0", NODE_HASH),
                ("22.12.0", "0" * 64),
            ]:
                changed = copy.deepcopy(receipt)
                changed["browser"].update(node_version=version, node_sha256=digest)
                with self.subTest(role=role, version=version, digest=digest):
                    with self.assertRaises(ValueError) as caught:
                        validate_receipt(changed, plan, sha(PLAN_PATH))
                    self.assertIn("diagnostic Node", str(caught.exception))

    def test_actual_node_wrong_hash_never_executes(self):
        receipt = json.loads((BUILT / "evidence/built-A.json").read_bytes())
        with patch("runtime_identity.sha", return_value="0" * 64), patch(
            "runtime_identity.subprocess.check_output"
        ) as run:
            with self.assertRaisesRegex(ValueError, "executable hash"):
                verify_runtime_identity(Path("/fixture/node"), receipt)
            run.assert_not_called()

    def test_actual_node_wrong_version_never_imports_playwright(self):
        receipt = json.loads((BUILT / "evidence/built-A.json").read_bytes())
        with patch("runtime_identity.sha", return_value=NODE_HASH), patch(
            "runtime_identity.subprocess.check_output", return_value="v22.12.0\n"
        ) as run:
            with self.assertRaisesRegex(ValueError, "version differs"):
                verify_runtime_identity(Path("/fixture/node"), receipt)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], ["/fixture/node", "--version"])

    def test_corrected_overlay_and_original_plan_are_both_bound(self):
        plan = json.loads(PLAN_PATH.read_bytes())
        # Historical overlays intentionally reject source changed by this unbuilt layer.
        with self.assertRaisesRegex(ValueError, "overlay drift"):
            verify_runtime_overlay(plan)
        from correction import verify_correction

        verify_correction()
        with patch(
            "runtime_identity.sha", return_value="0" * 64
        ), self.assertRaisesRegex(ValueError, "overlay drift"):
            verify_runtime_overlay(plan)
        plan["overlay_files"]["launcher.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "original runtime overlay"):
            verify_runtime_overlay(plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
