"""Initialize only a new, explicitly marked private training volume."""

import importlib.util
import json
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "operator_training_scenario", Path(__file__).with_name("scenario.py")
)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)
root = Path("/app/data")
source = json.loads(Path("/training-marker.json").read_text())
# Validate the supplied marker through the same strict schema without adopting data.
if (
    os.getenv("STARLINK_MODE") != "simulation"
    or os.getenv("OPERATOR_TRAINING_FIXTURE") != "explicit-private-training-v1"
):
    raise RuntimeError("Explicit private simulation training required")
marker = root / scenario.MARKER
if marker.exists():
    scenario.training_namespace(root, mode="simulation")
    if json.loads(marker.read_text()) != source:
        raise RuntimeError("Training volume identity differs; preserve for recovery")
else:
    if any(path.is_file() or path.is_symlink() for path in root.rglob("*")):
        raise RuntimeError(
            "Unmarked volume contains files; refuse to adopt or reset it"
        )
    marker.write_text(json.dumps(source, indent=2))
    scenario.training_namespace(root, mode="simulation")
os.chown(root, 1000, 1000)
os.chmod(root, 0o700)
os.chown(marker, 1000, 1000)
os.chmod(marker, 0o600)
