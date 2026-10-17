"""A commit acknowledgement failure cannot claim the accepted command was lost."""

import sqlite3
from uuid import uuid4

from app.operator.runtime import OperatorRuntime
from tests.operator.api_helpers import BASE, create


def test_real_commit_then_io_failure_is_uncertain_and_reopen_replays_once(
    api, record_data, clock, monkeypatch
):
    runtime = api.app.state.operator_runtime
    store = runtime.service.store
    connect = store._connection

    class CommitThenFail:
        def __init__(self):
            self.connection = connect()
            self.writing = False

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, sql, *args):
            if sql == "BEGIN IMMEDIATE":
                self.writing = True
            return self.connection.execute(sql, *args)

        def commit(self):
            self.connection.commit()
            if self.writing:
                error = sqlite3.OperationalError("private SQL path acknowledgement")
                error.sqlite_errorcode = sqlite3.SQLITE_IOERR
                raise error

    monkeypatch.setattr(store, "_connection", CommitThenFail)
    key = str(uuid4())
    result = create(api, record_data, key)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "commit_outcome_unknown"
    assert result.json()["error"]["retryable"] is True
    assert "private" not in result.text
    assert not store.health().ready
    retry = create(api, record_data, key)
    assert retry.status_code == 503
    assert retry.json()["error"]["retryable"] is True
    runtime.close()
    reopened = OperatorRuntime.start(store.settings, clock=clock)
    api.app.state.operator_runtime = reopened
    try:
        result = create(api, record_data, key)
        assert result.status_code == 201
        assert result.headers["Idempotency-Replayed"] == "true"
        history = api.get(BASE + "/journal?mission_id=demo-mission").json()
        assert len(history["items"]) == 1
        assert history["items"][0]["record"] == result.json()["saved_records"][0]
    finally:
        reopened.close()
