"""One behavioral compatibility case, using retained plan/checkpoint inputs."""

import copy
import json
import unittest
from comparison import compare, approved_correction, BUILT, prepare


class ComparisonTests(unittest.TestCase):
    def test_only_approved_superseded_hashes_are_accepted(self):
        original = json.loads((BUILT / "evidence/runtime-build-plan.json").read_bytes())
        approved, provenance = approved_correction()
        generated = copy.deepcopy(original)
        for role in ("A", "C"):
            generated["roles"][role]["compose_sha256"]["override"] = (
                prepare.build.digest(
                    (
                        json.dumps(prepare.compose(role)[1], sort_keys=True, indent=2)
                        + "\n"
                    ).encode()
                )
            )
        before = copy.deepcopy(original)
        self.assertEqual(compare(generated, original)["correction"], provenance)
        self.assertEqual(original, before)
        for path in [
            ("roles", "A", "compose_sha256", "override"),
            ("roles", "C", "compose_sha256", "override"),
            ("roles", "A", "context_sha256"),
            ("overlay_sha256",),
        ]:
            changed = copy.deepcopy(generated)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "0" * 64
            with self.subTest(path=path), self.assertRaises(ValueError):
                compare(changed, original)
        changed = copy.deepcopy(generated)
        changed["unexpected"] = True
        with self.assertRaises(ValueError):
            compare(changed, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
