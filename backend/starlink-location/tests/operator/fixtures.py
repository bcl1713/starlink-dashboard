"""Load the same synthetic fixture used by the acceptance-only startup wrapper."""

import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[4] / "tools/acceptance/operator-journal"
sys.path.insert(0, str(HARNESS))

from scenario import ScenarioClock, make_demo, pop_inputs
from seed import seed_demo

__all__ = ["ScenarioClock", "make_demo", "pop_inputs", "seed_demo"]
