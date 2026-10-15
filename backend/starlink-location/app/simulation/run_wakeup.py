"""Wake the single producer after a committed run replaces ordinary collection."""

import asyncio


class ReplayWakeup:
    def __init__(self):
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()

    def wake(self) -> None:
        self._loop.call_soon_threadsafe(self._event.set)

    async def wait(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._event.wait(), timeout=delay)
        except TimeoutError:
            pass
        finally:
            self._event.clear()
