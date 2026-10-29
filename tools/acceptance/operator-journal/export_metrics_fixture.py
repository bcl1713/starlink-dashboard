"""Fresh synthetic acquisitions feed the production metric publication path."""

import asyncio


async def publish_metrics(main, stop):
    def refresh():
        main._coordinator.update()
        main._refresh_metrics_without_collection(initial=True)

    while not stop.is_set():
        work = asyncio.create_task(asyncio.to_thread(refresh))
        try:
            await asyncio.shield(work)
        except asyncio.CancelledError:
            await asyncio.gather(work, return_exceptions=True)
            raise
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.1)
        except asyncio.TimeoutError:
            pass
