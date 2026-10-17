"""Operator application boundary: receipt-first retries and canonical lock order."""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from . import commands, queries
from .clock import Clock
from .errors import OperatorError
from .maintenance import capacity_status
from .models import (
    Actor,
    CommandReceipt,
    CreateRecord,
    HistoryPage,
    OperatorCommand,
    RecordFilter,
    RecordPage,
    SavedRecord,
)
from .references import MissionReferences
from .store import OperatorStore


@dataclass(frozen=True)
class ExecutionResult:
    receipt: CommandReceipt
    replayed: bool


class OperatorService:
    def __init__(
        self,
        store: OperatorStore,
        *,
        clock: Clock,
        actor: Actor,
        references: MissionReferences,
    ):
        self.store, self.clock, self.actor, self.references = (
            store,
            clock,
            actor,
            references,
        )

    def execute(
        self, command: OperatorCommand, *, key: str, epoch: str
    ) -> CommandReceipt:
        return self.execute_result(command, key=key, epoch=epoch).receipt

    def execute_result(
        self,
        command: OperatorCommand,
        *,
        key: str,
        epoch: str,
        writable_types: set[str] | None = None,
    ) -> ExecutionResult:
        identity = self.store.health()
        if not epoch:
            raise OperatorError("validation_error", fields={"epoch": "Required"})
        if epoch != str(identity.api_epoch):
            raise OperatorError("store_epoch_changed")
        try:
            key = str(UUID(key))
        except (ValueError, TypeError, AttributeError) as error:
            raise OperatorError(
                "validation_error", fields={"key": "Expected UUID"}
            ) from error
        encoded = json.dumps(
            command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        if len(encoded) > 65536:
            raise OperatorError(
                "validation_error", fields={"body": "Body exceeds 64 KiB"}
            )
        request_hash = hashlib.sha256(encoded).hexdigest()
        with self.store.connect() as connection:
            receipt = commands.receipt_for_key(connection, key, request_hash)
            if receipt is not None:
                return ExecutionResult(receipt, replayed=True)
            current = (
                None
                if isinstance(command, CreateRecord)
                else queries.get_record(connection, command.record_id)
            )
        mission_ids = [current.mission_id] if current else []
        if command.operation in ("create", "update"):
            mission_ids.append(command.mission_id)
        with self.references.locked(mission_ids), self.store.connect(
            write=True
        ) as connection:
            receipt = commands.receipt_for_key(connection, key, request_hash)
            if receipt is not None:
                return ExecutionResult(receipt, replayed=True)
            if capacity_status(self.store)["exceeded"]:
                raise OperatorError("capacity_exceeded")
            if current:
                current = queries.get_record(connection, command.record_id)
            if writable_types is not None and (
                (current is not None and current.record_type not in writable_types)
                or (
                    hasattr(command, "record_type")
                    and command.record_type not in writable_types
                )
            ):
                raise OperatorError(
                    "validation_error",
                    fields={"record_type": "Workflow is not publicly editable"},
                )
            if current and current.version != command.expected_version:
                raise OperatorError("version_conflict", current_version=current.version)
            target = command if command.operation in ("create", "update") else current
            if command.operation != "remove":
                self.references.validate(
                    target.mission_id, target.leg_id, target.scope, target.payload
                )
            receipt = commands.execute_in_transaction(
                connection,
                command,
                key=key,
                request_hash=request_hash,
                clock=self.clock,
                actor=self.actor,
            )
            return ExecutionResult(receipt, replayed=False)

    def get(self, record_id: str) -> SavedRecord:
        with self.store.connect() as connection:
            return queries.get_record(connection, record_id)

    def _page(self, kind, filters, *, limit, cursor):
        with self.store.connect() as connection:
            return queries.page(
                connection,
                identity=self.store.health(),
                clock=self.clock,
                kind=kind,
                filters=filters,
                limit=limit,
                cursor=cursor,
            )

    def list(self, filters: RecordFilter, *, limit=50, cursor=None) -> RecordPage:
        return self._page(
            "records", filters.model_dump(mode="json"), limit=limit, cursor=cursor
        )

    def history(self, record_id: str, *, limit=50, cursor=None) -> HistoryPage:
        # Distinguish an absent record from an existing empty history page.
        self.get(record_id)
        return self._page(
            "history", {"record_id": str(record_id)}, limit=limit, cursor=cursor
        )

    def journal(self, mission_id: str, *, limit=50, cursor=None) -> HistoryPage:
        return self._page(
            "journal", {"mission_id": mission_id}, limit=limit, cursor=cursor
        )
