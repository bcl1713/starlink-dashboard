"""Common local admission for current model inputs and their mutation paths."""

from functools import wraps


def model_input_write(function):
    """Keep the existing repository-first order, including legacy input writers."""

    @wraps(function)
    def guarded(*args, **kwargs):
        from app.mission.storage import get_active_leg_lock

        with get_active_leg_lock():
            return function(*args, **kwargs)

    return guarded
