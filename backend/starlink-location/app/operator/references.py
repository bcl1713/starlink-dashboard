"""Canonical planning gates and typed Operator relationship integrity."""

from contextlib import ExitStack, contextmanager

from filelock import Timeout

from app.mission import storage

from .errors import OperatorError


def derive_links(record) -> set[tuple[str, str, str]]:
    """Derive the complete active link index; recovery shares this definition."""
    if record.deleted:
        return set()
    relations = {
        "call": (("conference_id", "call-to-conference"),),
        "participation": (
            ("call_id", "participation-to-call"),
            ("conference_id", "participation-to-conference"),
            ("resumes_participation_id", "participation-resumes"),
        ),
    }
    return {
        (str(record.record_id), relation, str(target))
        for field, relation in relations.get(record.record_type, ())
        if (target := getattr(record.payload, field)) is not None
    }


class MissionReferences:
    def _load(self, mission_id):
        try:
            return storage.load_mission_v2(mission_id)
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            # The planning loader assigns decoded metadata fields before model
            # validation; a non-object JSON root raises TypeError at that step.
            raise OperatorError("store_unavailable") from error

    @staticmethod
    def _missing_legs(mission, leg_id, payload):
        legs = {leg.id for leg in mission.legs}
        requested = {
            "leg_id": leg_id,
            "payload.previous_leg_id": payload.previous_leg_id,
            "payload.next_leg_id": payload.next_leg_id,
        }
        return [
            name
            for name, value in requested.items()
            if value is not None and value not in legs
        ]

    def resolve(self, record) -> dict:
        """Derived association state; missing storage never proves deletion."""
        try:
            mission = self._load(record.mission_id)
        except OperatorError:
            return {
                "status": "unknown",
                "unresolved_fields": [],
                "error_code": "planning_unavailable",
            }
        missing = (
            ["mission_id"]
            if mission is None
            else self._missing_legs(mission, record.leg_id, record.payload)
        )
        return {
            "status": "missing" if missing else "resolved",
            "unresolved_fields": missing,
            "error_code": None,
        }

    @contextmanager
    def locked(self, mission_ids: list[str]):
        try:
            with ExitStack() as stack:
                stack.enter_context(storage.get_active_leg_lock().acquire(timeout=2))
                for mission_id in sorted(set(mission_ids)):
                    stack.enter_context(
                        storage.get_mission_lock(mission_id).acquire(timeout=2)
                    )
                yield
        except Timeout as error:
            raise OperatorError("store_busy", retryable=True) from error

    def validate(self, mission_id, leg_id, scope, payload) -> None:
        mission = self._load(mission_id)
        if mission is None:
            raise OperatorError(
                "validation_error", fields={"mission_id": "Mission does not exist"}
            )
        missing = {
            name: "Leg does not belong to mission"
            for name in self._missing_legs(mission, leg_id, payload)
        }
        if missing:
            raise OperatorError("validation_error", fields=missing)


def validate_dependencies(connection, changed) -> None:
    """Validate both ends of every relationship affected by this replacement."""
    from .queries import get_record

    affected = {str(changed.record_id): changed}
    for (source,) in connection.execute(
        "SELECT DISTINCT from_id FROM current_links WHERE to_id=?",
        (str(changed.record_id),),
    ):
        affected[source] = get_record(connection, source)
    conflicts = set()
    for record in affected.values():
        for source, relation, target_id in derive_links(record):
            target = affected.get(target_id)
            if target is None:
                try:
                    target = get_record(connection, target_id)
                except OperatorError as error:
                    if error.code != "record_not_found":
                        raise
            expected_type = {
                "participation-to-call": "call",
                "participation-resumes": "participation",
            }.get(relation, "conference")
            if (
                target is None
                or target.deleted
                or target.record_type != expected_type
                or target.mission_id != record.mission_id
                or source == target_id
            ):
                conflicts.update((source, target_id))
                continue
            if relation == "participation-resumes":
                if (
                    target.payload.state != "interrupted"
                    or target.payload.call_id != record.payload.call_id
                    or target.payload.conference_id != record.payload.conference_id
                ):
                    conflicts.update((source, target_id))
                visited = {source}
                ancestor = target
                while ancestor is not None:
                    ancestor_id = str(ancestor.record_id)
                    if ancestor_id in visited:
                        conflicts.update(visited)
                        break
                    visited.add(ancestor_id)
                    parent_id = ancestor.payload.resumes_participation_id
                    if parent_id is None:
                        break
                    ancestor = affected.get(str(parent_id))
                    if ancestor is None:
                        try:
                            ancestor = get_record(connection, parent_id)
                        except OperatorError:
                            conflicts.update(visited)
                            break
    if conflicts:
        raise OperatorError("dependency_conflict", record_ids=sorted(conflicts))
