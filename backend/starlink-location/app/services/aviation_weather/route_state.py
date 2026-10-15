"""Bounded process-safe sibling persistence for route-specific SIGMET notices.

Async methods move the entire file-lock/I/O operation to a worker thread. The
sync methods are for callers already inside asyncio.to_thread, holding the outer
active-leg lock. Their optional validate callback runs INSIDE the notice lock,
before mutation: use only current in-memory route/feed/UTC checks, without
acquiring other locks or doing network/worker I/O. The service must validate
current eligibility there; this store knows registered, unexpired records only.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Self

from filelock import FileLock, Timeout
from pydantic import Field, ValidationError, model_validator

from app.models.aviation_weather import Contract, Hash, Time
from app.models.route_sigmets import NoticeConfirmation, NoticeMutation, NoticeSelection
from app.services.aviation_weather.route_identity import BulletinGroup, notice_key

MAX_CONTEXTS = 8
MAX_RECORDS = 4000
MAX_STATE_BYTES = 2 * 1024**2


class NoticeStoreUnavailable(RuntimeError):
    """A bounded state read/write could not safely complete."""


class NoticeCapacityError(NoticeStoreUnavailable):
    """Capacity cannot be recovered without evicting current live records."""


class NoticeConflict(RuntimeError):
    """The requested notice or its current identity is no longer eligible."""


class ContextRecord(Contract):
    last_used_revision: Time


class NoticeRecord(Contract):
    context_key: Hash
    bulletin_key: Hash
    semantic_digest: Hash
    valid_from_ms: Time
    expires_at_ms: Time
    acknowledged: bool
    selected: bool = False
    attention_order: Time


class NoticeState(Contract):
    schema_version: Literal["route-sigmet-state-v2"] = Field(
        default="route-sigmet-state-v2", alias="schema"
    )
    state_revision: Time = 0
    attention_counter: Time = 0
    contexts: dict[Hash, ContextRecord] = Field(default_factory=dict)
    records: dict[Hash, NoticeRecord] = Field(default_factory=dict)

    @model_validator(mode="after")
    def integrity(self) -> Self:
        if len(self.contexts) > MAX_CONTEXTS or len(self.records) > MAX_RECORDS:
            raise ValueError("Notice state exceeds capacity")
        for key, record in self.records.items():
            if (
                record.context_key not in self.contexts
                or record.valid_from_ms >= record.expires_at_ms
                or not 0 < record.attention_order <= self.attention_counter
                or key
                != notice_key(
                    record.context_key, record.bulletin_key, record.semantic_digest
                )
            ):
                raise ValueError("Invalid notice state record")
        return self


Validator = Callable[[], None]


class NoticeStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = FileLock(f"{self.path}.lock", timeout=1)

    async def reconcile(
        self,
        context_key: str,
        eligible: list[BulletinGroup],
        now_ms: int,
        *,
        validate: Validator | None = None,
    ) -> NoticeState:
        return await asyncio.to_thread(
            self.reconcile_sync, context_key, eligible, now_ms, validate=validate
        )

    async def set_ack(
        self, change: NoticeMutation, now_ms: int, *, validate: Validator | None = None
    ) -> NoticeConfirmation:
        return await asyncio.to_thread(
            self.set_ack_sync, change, now_ms, validate=validate
        )

    def _read(self) -> NoticeState:
        try:
            with self.path.open("rb") as stream:
                body = stream.read(MAX_STATE_BYTES + 1)
        except FileNotFoundError:
            return NoticeState()
        if len(body) > MAX_STATE_BYTES:
            raise ValueError("Oversized notice state")
        # Do not silently repair or overwrite unknown/corrupt persistent state.
        required = {
            "schema",
            "state_revision",
            "attention_counter",
            "contexts",
            "records",
        }
        raw = json.loads(body)
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError("Incomplete notice state")
        if raw.get('schema') == 'route-sigmet-state-v1':
            # Migration is validated before replacing the old file, under its lock.
            # Old records must not contain fields added by a newer schema.
            for record in raw.get('records', {}).values():
                if 'selected' in record:
                    raise ValueError('Invalid v1 notice record')
            raw['schema'] = 'route-sigmet-state-v2'
            migrated = NoticeState.model_validate(raw)
            self._write(migrated)
            return migrated
        return NoticeState.model_validate(raw)

    @staticmethod
    def _prune(state: NoticeState, now_ms: int) -> NoticeState:
        return state.model_copy(
            update={
                "records": {
                    key: record
                    for key, record in state.records.items()
                    if record.expires_at_ms > now_ms
                }
            }
        )

    @staticmethod
    def _body(state: NoticeState) -> bytes:
        return (state.model_dump_json(by_alias=True) + "\n").encode("utf-8")

    def _bounded(self, state: NoticeState, context_key: str) -> NoticeState:
        contexts, records = dict(state.contexts), dict(state.records)
        while True:
            candidate = state.model_copy(
                update={"contexts": contexts, "records": records}
            )
            if (
                len(contexts) <= MAX_CONTEXTS
                and len(records) <= MAX_RECORDS
                and len(self._body(candidate)) <= MAX_STATE_BYTES
            ):
                return NoticeState.model_validate(candidate.model_dump(by_alias=True))
            inactive = [key for key in contexts if key != context_key]
            if not inactive:
                raise NoticeCapacityError("Route SIGMET notice state capacity reached")
            victim = min(
                inactive, key=lambda key: (contexts[key].last_used_revision, key)
            )
            del contexts[victim]
            records = {
                key: record
                for key, record in records.items()
                if record.context_key != victim
            }

    def _write(self, state: NoticeState) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(self._body(state))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _commit(
        self, old: NoticeState, state: NoticeState, context_key: str
    ) -> NoticeState:
        if state == old:
            return old
        state = state.model_copy(update={"state_revision": old.state_revision + 1})
        state = self._bounded(state, context_key)
        self._write(state)
        return state

    def reconcile_sync(
        self,
        context_key: str,
        eligible: list[BulletinGroup],
        now_ms: int,
        *,
        validate: Validator | None = None,
        selection_eligible: list[BulletinGroup] | None = None,
    ) -> NoticeState:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                old = self._read()
                if validate is not None:
                    validate()
                state = self._prune(old, now_ms)
                contexts = dict(state.contexts)
                # Touch only on context switches; repeated polls/retries are no-ops.
                latest = max(
                    contexts,
                    key=lambda key: (contexts[key].last_used_revision, key),
                    default=None,
                )
                if latest != context_key:
                    contexts[context_key] = ContextRecord(
                        last_used_revision=old.state_revision + 1
                    )
                records = dict(state.records)
                counter = state.attention_counter
                selected_keys = {
                    record.bulletin_key for record in records.values()
                    if record.context_key == context_key and record.selected
                    and not record.acknowledged
                }
                selected_groups = {
                    group.notice_key(context_key): group
                    for group in (selection_eligible or [])
                    if group.bulletin_key in selected_keys and not group.identity_uncertain
                }
                if selection_eligible is not None:
                    for key, record in list(records.items()):
                        if record.context_key == context_key and record.selected and key not in selected_groups:
                            records[key] = record.model_copy(update={'selected': False})
                candidates = {group.notice_key(context_key): group for group in eligible}
                candidates.update(selected_groups)
                for key, group in candidates.items():
                    if not group.valid_from_ms <= now_ms < group.expires_at_ms:
                        continue
                    if key not in records:
                        counter += 1
                        records[key] = NoticeRecord(
                            context_key=context_key,
                            bulletin_key=group.bulletin_key,
                            semantic_digest=group.semantic_digest,
                            valid_from_ms=group.valid_from_ms,
                            expires_at_ms=group.expires_at_ms,
                            acknowledged=False,
                            selected=key in selected_groups,
                            attention_order=counter,
                        )
                    elif key in selected_groups and not records[key].selected:
                        records[key] = records[key].model_copy(update={'selected': True})
                state = state.model_copy(
                    update={
                        "contexts": contexts,
                        "records": records,
                        "attention_counter": counter,
                    }
                )
                return self._commit(old, state, context_key)
        except (OSError, Timeout, ValueError, ValidationError) as exc:
            raise NoticeStoreUnavailable(
                "Route SIGMET notice state unavailable"
            ) from exc

    def select_sync(
        self, change: NoticeSelection, group: BulletinGroup, now_ms: int,
        *, validate: Validator | None = None,
    ) -> NoticeState:
        if (change.bulletin_key != group.bulletin_key
            or change.semantic_digest != group.semantic_digest
            or not group.valid_from_ms <= now_ms < group.expires_at_ms):
            raise NoticeConflict('SIGMET selection is no longer current')
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                old = self._read()
                if validate is not None:
                    validate()
                state = self._prune(old, now_ms)
                contexts = dict(state.contexts)
                contexts[change.context_key] = ContextRecord(last_used_revision=old.state_revision + 1)
                key = group.notice_key(change.context_key)
                record = state.records.get(key)
                if record and record.selected and not record.acknowledged:
                    return state
                counter = state.attention_counter + (record is None or record.acknowledged)
                record = NoticeRecord(
                    context_key=change.context_key, bulletin_key=group.bulletin_key,
                    semantic_digest=group.semantic_digest, valid_from_ms=group.valid_from_ms,
                    expires_at_ms=group.expires_at_ms, acknowledged=False, selected=True,
                    attention_order=counter if record is None or record.acknowledged else record.attention_order,
                )
                state = state.model_copy(update={
                    'contexts': contexts, 'records': {**state.records, key: record},
                    'attention_counter': counter,
                })
                return self._commit(old, state, change.context_key)
        except (OSError, Timeout, ValueError, ValidationError) as exc:
            raise NoticeStoreUnavailable('SIGMET selection state unavailable') from exc

    def set_ack_sync(
        self, change: NoticeMutation, now_ms: int, *, validate: Validator | None = None
    ) -> NoticeConfirmation:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                old = self._read()
                if validate is not None:
                    validate()
                state = self._prune(old, now_ms)
                record = state.records.get(change.notice_key)
                if (
                    record is None
                    or record.context_key != change.context_key
                    or record.semantic_digest != change.semantic_digest
                    or not record.valid_from_ms <= now_ms < record.expires_at_ms
                ):
                    raise NoticeConflict("Route SIGMET notice is no longer current")
                if record.acknowledged != change.acknowledged:
                    counter = state.attention_counter + (not change.acknowledged)
                    record = record.model_copy(
                        update={
                            "acknowledged": change.acknowledged,
                            "selected": False if change.acknowledged else record.selected,
                            "attention_order": (
                                counter
                                if not change.acknowledged
                                else record.attention_order
                            ),
                        }
                    )
                    state = state.model_copy(
                        update={
                            "attention_counter": counter,
                            "records": {**state.records, change.notice_key: record},
                        }
                    )
                state = self._commit(old, state, change.context_key)
                return NoticeConfirmation(
                    **change.model_dump(),
                    state_revision=state.state_revision,
                    attention_order=record.attention_order,
                )
        except (OSError, Timeout, ValueError, ValidationError) as exc:
            raise NoticeStoreUnavailable(
                "Route SIGMET notice state unavailable"
            ) from exc
