"""Cooperative cancellation shared by export builders and request workers."""


class ExportCancelled(RuntimeError):
    """Request cancellation stops work before publishing a download."""


def check_cancelled(cancel):
    if cancel is not None and cancel.is_set():
        raise ExportCancelled("Export cancelled")
