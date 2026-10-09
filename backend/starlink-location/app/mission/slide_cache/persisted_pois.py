"""Read committed POIs without mutating process-local manager caches."""

import json
from pathlib import Path

from filelock import FileLock

from app.models.poi import POI
from app.services.poi_manager import POIManager


class PersistedPOIs:
    def __init__(self, manager):
        self.path = Path(manager.pois_file)
        self.lock_file = str(manager.lock_file)

    def list_pois(self):
        # capture_inputs reads this twice, detecting intervening persisted edits.
        with FileLock(self.lock_file, timeout=5):
            raw = json.loads(self.path.read_bytes())
        return [
            POI.model_validate(value)
            for _, value in sorted(raw.get("pois", {}).items())
        ]


def persisted_pois(manager):
    return PersistedPOIs(manager) if isinstance(manager, POIManager) else manager
