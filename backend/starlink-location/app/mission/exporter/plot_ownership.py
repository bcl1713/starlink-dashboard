"""Serialize legacy Matplotlib state without blocking the asynchronous API loop."""

import threading
from contextvars import ContextVar
from functools import wraps

from app.mission.exporter.export_cancel import check_cancelled

PLOT_LOCK = threading.RLock()
PLOT_CANCEL = ContextVar("legacy_plot_cancel", default=None)


def export_plot_context(function):
    @wraps(function)
    def owned(*args, **kwargs):
        token = PLOT_CANCEL.set(kwargs.get("cancel"))
        try:
            return function(*args, **kwargs)
        finally:
            PLOT_CANCEL.reset(token)

    return owned


def serialized_plot(function):
    @wraps(function)
    def owned(*args, **kwargs):
        cancel = PLOT_CANCEL.get()
        check_cancelled(cancel)
        while not PLOT_LOCK.acquire(timeout=0.05):
            check_cancelled(cancel)
        try:
            check_cancelled(cancel)
            import matplotlib.pyplot as plt

            figures = set(plt.get_fignums())
            try:
                return function(*args, **kwargs)
            finally:
                for number in set(plt.get_fignums()) - figures:
                    plt.close(number)
        finally:
            PLOT_LOCK.release()

    return owned
