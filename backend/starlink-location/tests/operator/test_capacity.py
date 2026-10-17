"""Capacity never erases history; persistent media failures disable writes."""

import sqlite3
from dataclasses import replace

import pytest

from app.operator.errors import OperatorError
from app.operator.models import CreateRecord
from tests.operator.service_helpers import submit


def test_capacity_advisory_and_rejection(service, record_data):
    from app.operator.maintenance import capacity_status

    command = CreateRecord.model_validate(record_data)
    receipt = submit(service, command, key="00000000-0000-4000-8000-000000000001")
    used = capacity_status(service.store)["used_bytes"]
    service.store.settings = replace(
        service.store.settings, capacity_bytes=used * 5 // 4
    )
    assert capacity_status(service.store)["advisory"] is True
    service.store.settings = replace(service.store.settings, capacity_bytes=used)
    with pytest.raises(OperatorError) as error:
        submit(service, command)
    assert error.value.code == "capacity_exceeded"
    assert (
        submit(service, command, key="00000000-0000-4000-8000-000000000001") == receipt
    )
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 1


@pytest.mark.parametrize(
    "code", [sqlite3.SQLITE_FULL, sqlite3.SQLITE_READONLY, sqlite3.SQLITE_IOERR]
)
def test_storage_error_disables_until_reopen(service, record_data, monkeypatch, code):
    from app.operator import commands

    real = commands._persist_changes

    def media_failure(*args, **kwargs):
        real(*args, **kwargs)
        error = sqlite3.OperationalError("injected storage failure")
        error.sqlite_errorcode = code
        raise error

    monkeypatch.setattr(commands, "_persist_changes", media_failure)
    with pytest.raises(OperatorError) as error:
        submit(service, CreateRecord.model_validate(record_data))
    assert error.value.code == "store_unavailable"
    assert not service.store.health().ready
    with sqlite3.connect(service.store.settings.database_path) as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "code,retryable", [(sqlite3.SQLITE_BUSY, True), (sqlite3.SQLITE_IOERR, False)]
)
def test_commit_failure_never_acknowledges(
    service, record_data, monkeypatch, code, retryable
):
    real = service.store._connection

    class FailedCommit:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def commit(self):
            if self.connection.total_changes:
                error = sqlite3.OperationalError("injected commit failure")
                error.sqlite_errorcode = code
                raise error
            self.connection.commit()

    monkeypatch.setattr(service.store, "_connection", lambda: FailedCommit(real()))
    with pytest.raises(OperatorError) as error:
        submit(service, CreateRecord.model_validate(record_data))
    assert error.value.retryable == retryable
    assert service.store.health().ready == retryable
    with sqlite3.connect(service.store.settings.database_path) as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0


def test_capacity_rechecked_after_writer_admission(service, record_data, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from uuid import uuid4

    from app.operator import commands
    from app.operator.maintenance import capacity_status
    from app.operator.models import Actor

    reached = Event()
    real = service.store._connection

    class WaitingWriter:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, sql, parameters=()):
            if sql == "BEGIN IMMEDIATE":
                reached.set()
            return self.connection.execute(sql, parameters)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with service.store.connect(write=True) as writer:
            used = capacity_status(service.store)["used_bytes"]
            service.store.settings = replace(
                service.store.settings, capacity_bytes=used + 100
            )
            command = CreateRecord.model_validate(record_data)
            commands.execute_in_transaction(
                writer,
                command,
                key=str(uuid4()),
                request_hash="first",
                clock=service.clock,
                actor=Actor(),
            )
            monkeypatch.setattr(
                service.store, "_connection", lambda: WaitingWriter(real())
            )
            pending = pool.submit(submit, service, command)
            assert reached.wait(timeout=5)
        with pytest.raises(OperatorError, match="capacity_exceeded"):
            pending.result(timeout=5)
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 1
