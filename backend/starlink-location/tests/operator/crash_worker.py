"""Disposable subprocess fault barriers; never imported by production code."""

import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.mission import storage
from app.operator.models import Actor, CreateRecord, UpdateRecord
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from tests.operator.conftest import FakeClock


def main():
    config = json.loads(Path(sys.argv[1]).read_text())
    descriptor = int(sys.argv[2])
    clock = FakeClock(datetime(2026, 10, 17, 16, tzinfo=timezone.utc))
    settings = OperatorSettings(enabled=True, root=Path(config["root"]))

    def stop(event):
        os.write(descriptor, (json.dumps(event) + "\n").encode())
        while True:
            signal.pause()

    if config["mode"] == "initialize":
        from app.operator import store as module

        if config["barrier"] == "marker":
            real = module._write_marker

            def marker(path, identity, *, first):
                if not first:
                    stop({"barrier": "marker"})
                real(path, identity, first=first)

            module._write_marker = marker
        else:
            real = module.apply_migrations

            def migrate(db, **kwargs):
                real(db, **kwargs)
                stop({"barrier": "migration"})

            module.apply_migrations = migrate
        OperatorStore.open(settings, initialize=True, clock=clock)
        return
    store = OperatorStore.open(settings, initialize=False, clock=clock)
    if config["mode"] == "hold":
        with store.connect(write=config.get("write", False)):
            stop({"barrier": "hold"})
    storage.MISSIONS_DIR = Path(config["missions"])
    service = OperatorService(
        store, clock=clock, actor=Actor(), references=MissionReferences()
    )
    from app.operator import commands

    real = commands._persist_changes
    event = {}

    class BarrierConnection:
        def __init__(self, db):
            self.db = db

        def execute(self, sql, parameters=()):
            result = self.db.execute(sql, parameters)
            if sql.startswith(config["barrier"]):
                stop(event)
            return result

        def commit(self):
            if self.db.total_changes and config["barrier"] == "before_commit":
                stop(event)
            self.db.commit()
            if self.db.total_changes and config["barrier"] == "after_commit":
                stop(event)

        def __getattr__(self, name):
            return getattr(self.db, name)

    def persistence(db, changes, receipt, **kwargs):
        event.update(receipt=receipt.model_dump(mode="json"))
        return real(db, changes, receipt, **kwargs)

    commands._persist_changes = persistence
    connect = store._connection
    store._connection = lambda: BarrierConnection(connect())
    # Keep SQLite from checkpointing on its last normal connection close.
    keeper = connect() if config["barrier"] == "after_ack" else None
    try:
        acknowledged = []
        if config["mode"] == "reuse":
            for _ in range(4):
                filler = CreateRecord(
                    record_type="journal_entry",
                    mission_id="demo-mission",
                    scope="mission",
                    time=config["command"]["time"],
                    payload={
                        "entry_type": "note",
                        "title": "Filler",
                        "note": "x" * 8000,
                    },
                )
                saved = service.execute(filler, key=str(uuid4()), epoch=config["epoch"])
                acknowledged.append(str(saved.command_id))
            assert keeper.execute("PRAGMA wal_checkpoint(RESTART)").fetchone()[0] == 0
        result = service.execute(
            UpdateRecord.model_validate(config["command"]),
            key=config["key"],
            epoch=config["epoch"],
        )
        if config["barrier"] == "after_ack":
            stop(
                {
                    "receipt": result.model_dump(mode="json"),
                    "acknowledged": acknowledged,
                }
            )
        raise AssertionError("Worker missed requested fault barrier")
    finally:
        if keeper is not None:
            keeper.close()


if __name__ == "__main__":
    main()
