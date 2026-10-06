"""Source-only test transport feeding the actual scientific child and publisher."""

import asyncio
import json
import signal
import sys
from pathlib import Path

from app.services.aviation_weather.gfs.ipc import GfsMailbox
from app.services.aviation_weather.gfs.store import GfsProductStore
from app.services.aviation_weather.gfs.worker import GfsWorker
from app.services.aviation_weather.settings import AviationSettingsStore
from tests.fixtures.gfs_fields import grib_bundle


class FixtureTransport:
    async def acquire(self, selection, stage):
        return grib_bundle(stage, pressure=selection.pressure_pa)

    async def aclose(self):
        pass


async def main():
    root = Path(sys.argv[1])
    settings = AviationSettingsStore(root / "settings.json", readonly=True)
    mailbox = GfsMailbox(root / "mailbox", settings)
    clock = lambda: json.loads((root / "clock.json").read_text()) / 1000
    store = GfsProductStore(
        root / "artifacts", mailbox.root, settings, clock=clock, require_demand=True
    )
    command = (
        [
            sys.executable,
            str(Path(__file__).with_name("gfs_blocked_decoder.py")),
            str(root / "decoder-ready.json"),
        ]
        if sys.argv[2] == "blocked"
        else None
    )
    worker = GfsWorker(
        mailbox, store, FixtureTransport(), clock=clock, decoder_command=command
    )
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, worker.stop)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
