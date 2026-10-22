"""Wrap only explicit call sites; invoke the original pool and its limiter once.

`role` is the event family (producer/worker/refresh), not application A/C, which
is fixed by probe configuration. Cancellation delivery never claims worker exit.
"""

from functools import partial

import backend_probe as probe


def invoke_sync(role, op_id, fn, *args, **kwargs):
    operation_type = {
        "producer": "tick",
        "refresh": "derived_refresh",
        "scrape": "scrape",
        "status": "lifecycle",
        "source_observer": "source_observer",
    }.get(role, probe.operation_type())
    family = role if role in ("producer", "refresh") else "worker"
    with probe.operation(op_id, operation_type):
        probe.mark(family + ".start")
        try:
            result = fn(*args, **kwargs)
        except BaseException as error:
            probe.mark(family + ".end", outcome=probe.outcome(error))
            raise
        probe.mark(family + ".end")
        return result


async def await_pool(role, op_id, pool, fn, *args, **kwargs):
    operation_type = {
        "refresh": "derived_refresh",
        "scrape": "scrape",
        "status": "lifecycle",
        "source_observer": "source_observer",
    }.get(role, probe.operation_type())
    family = "refresh" if role == "refresh" else "worker"
    with probe.operation(op_id, operation_type):
        probe.mark(family + ".dispatch")
        try:
            # Keep callable kwargs inside the original pool, as Starlette does.
            result = await pool(partial(invoke_sync, role, op_id, fn, *args, **kwargs))
        except BaseException as error:
            probe.mark(family + ".returned", outcome=probe.outcome(error))
            raise
        probe.mark(family + ".returned")
        return result
