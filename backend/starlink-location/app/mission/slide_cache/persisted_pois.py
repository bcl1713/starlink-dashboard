"""Read committed POIs without mutating process-local manager caches."""

import json
from pathlib import Path

from filelock import FileLock

from app.mission.storage import planning_read_gate
from app.models.poi import POI
from app.services.poi_manager import POIManager


class PersistedPOIs:
    def __init__(self, manager):
        self.path = Path(manager.pois_file)
        self.lock_file = str(manager.lock_file)

    @planning_read_gate
    def read_bytes(self):
        # capture_inputs reads this twice, detecting intervening persisted edits.
        with FileLock(self.lock_file, timeout=5):
            return self.path.read_bytes()

    def list_pois(self):
        raw = json.loads(self.read_bytes())
        return [
            POI.model_validate(value)
            for _, value in sorted(raw.get("pois", {}).items())
        ]


def persisted_pois(manager):
    return PersistedPOIs(manager) if isinstance(manager, POIManager) else manager
