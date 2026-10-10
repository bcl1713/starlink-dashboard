"""Planning failures retain status, machine-readable code and recovery action."""

from .models import PlanningError


class PlanningFailure(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, *, action=None, retryable=False
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error = PlanningError(
            code=code, message=message, action=action, retryable=retryable
        )


def conflict(message="Planning revision has changed; reload before saving"):
    return PlanningFailure(409, "planning_conflict", message, action="reload")
