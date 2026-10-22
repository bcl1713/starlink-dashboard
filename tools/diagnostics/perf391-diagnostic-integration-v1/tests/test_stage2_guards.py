"""The approved main producer is eligible; neighboring entry/config files are not."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


class Stage2Guards(unittest.TestCase):
    def test_exact_main_entrypoint_only(self):
        build.check_patch_path("backend/starlink-location/main.py")
        for path in (
            "backend/starlink-location/entrypoint.sh",
            "backend/starlink-location/other.py",
            "backend/starlink-location/Dockerfile",
        ):
            with self.assertRaises(build.GuardError):
                build.check_patch_path(path)
