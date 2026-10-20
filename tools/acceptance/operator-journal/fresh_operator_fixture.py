"""Fresh production app with no Operator DB seed, lifecycle patch or fake receipts."""

import os
from pathlib import Path

if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only" or os.getenv("STARLINK_MODE") != "simulation":
    raise RuntimeError("Explicit private synthetic simulation deployment required")

root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
os.environ["OPERATOR_ROOT"] = str(root / "operator")
os.environ["OPERATOR_SIMULATION_RUN_ID"] = "synthetic-fresh-install-v1"

from app.mission import storage

storage.MISSIONS_DIR = root / "missions"

# Use production main's normal lifespan, Operator binding, clock and source factories.
from main import app
