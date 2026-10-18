"""Apply one predefined training input checkpoint through the owned launcher."""

import importlib.util
import json
import sys
from pathlib import Path


def apply_checkpoint(root, checkpoint_id):
    spec = importlib.util.spec_from_file_location(
        "operator_training_scenario", Path(__file__).with_name("scenario.py")
    )
    scenario = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario)
    return scenario.apply_checkpoint(root, checkpoint_id)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: control.py MARKED_DATA_ROOT CHECKPOINT")
    print(json.dumps(apply_checkpoint(Path(sys.argv[1]), sys.argv[2]), indent=2))
