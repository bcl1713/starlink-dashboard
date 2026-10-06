"""Real publisher blocked on the shared settings/publication lock."""

import sys
from pathlib import Path

from app.models.aviation_grid import GridCandidate, GridDescriptor
from app.services.aviation_weather.gfs.store import GfsProductStore
from app.services.aviation_weather.settings import AviationSettingsStore
from tests.fixtures.gfs_fields import RUN

root, directory, revision = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
settings = AviationSettingsStore(root / "settings.json", readonly=True)
store = GfsProductStore(
    root / "artifacts", root / "mailbox", settings, clock=lambda: RUN / 1000
)
candidate = GridCandidate(
    GridDescriptor.model_validate_json((directory / "grid.json").read_bytes()),
    directory,
)
(root / "publisher-ready").touch()
try:
    store.publish(candidate, revision)
except ValueError:
    raise SystemExit(20) from None
