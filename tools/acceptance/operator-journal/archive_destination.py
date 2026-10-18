"""A separate, initially empty dashboard for portable plan-import acceptance."""

import os
from pathlib import Path

from scenario import ScenarioClock, RUN_ID
from app.mission import storage
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore

if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only":
    raise RuntimeError("Explicit synthetic acceptance required")
root = Path("/app/data")
storage.MISSIONS_DIR = root / "missions"
os.environ["OPERATOR_SIMULATION_RUN_ID"] = RUN_ID
os.environ["OPERATOR_ROOT"] = str(root / "operator")
store = OperatorStore.open(
    OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode="simulation",
        simulation_run_id=RUN_ID,
    ),
    initialize=True,
    clock=ScenarioClock(),
)
store.close()
from main import app  # noqa: E402,F401
