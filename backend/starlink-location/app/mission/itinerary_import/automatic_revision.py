"""Apply uploaded itinerary changes without an intermediate review workflow."""

from .revisions import stage_revision


def apply_revision(service, operation, prepared):
    for attempt in range(2):
        if operation.state in {"cancelled", "committed", "failed"}:
            return operation
        ready = stage_revision(service, operation, prepared)
        choices = {
            conflict["field"]: "replace"
            for conflict in ready.details["revision"]["conflicts"]
        }
        try:
            return service.commit_revision(ready.id, ready.generation, choices)
        except ValueError as error:
            if "stale" not in str(error) or attempt:
                raise
            # Capture a fresh live generation once; compatible manual edits stay.
            operation = service.store.read(ready.id)
    raise ValueError("Mission changed during update; retry")
