"""Salt corruption must never masquerade as SQLite's checkpointed old tail."""

import hashlib
import os
import signal
from pathlib import Path
from uuid import uuid4

import pytest

from app.operator.errors import OperatorError
from app.operator.models import CreateRecord
from app.operator.store import OperatorStore
from tests.operator.process_helpers import stopped_worker
from tests.operator.service_helpers import submit, update


def crashed_wal(service, record_data, tmp_path, *, mode, resets=None):
    receipt = submit(service, CreateRecord.model_validate(record_data))
    original = receipt.saved_records[0]
    command = update(service, original)
    config = {
        "mode": mode,
        "barrier": "after_ack",
        "root": str(service.store.settings.root),
        "missions": str(tmp_path / "missions"),
        "key": str(uuid4()),
        "epoch": str(service.store.health().api_epoch),
        "command": command.model_dump(mode="json"),
    }
    if resets is not None:
        config["resets"] = resets
    with stopped_worker(tmp_path, config) as (worker, event):
        os.killpg(worker.pid, signal.SIGKILL)
        assert worker.wait(timeout=5) == -signal.SIGKILL
    expected = event["receipt_hashes"] | {
        str(receipt.command_id): hashlib.sha256(
            receipt.model_dump_json().encode()
        ).hexdigest()
    }
    service.store.close()
    wal = Path(str(service.store.settings.database_path) + "-wal")
    return wal, wal.read_bytes(), expected


def assert_acknowledged_receipts(store, expected):
    with store.connect() as db:
        actual = {
            row[0]: hashlib.sha256(row[1].encode()).hexdigest()
            for row in db.execute("SELECT command_id, response_json FROM commands")
        }
        assert actual == expected
        assert {
            row[0] for row in db.execute("SELECT command_id FROM revisions")
        } == set(expected)


@pytest.mark.parametrize("salt_byte", range(8))
@pytest.mark.parametrize("position", ["first", "later"])
def test_active_salt_damage_refuses_or_preserves_every_acknowledgment(
    service, record_data, tmp_path, clock, salt_byte, position
):
    wal, data, expected = crashed_wal(service, record_data, tmp_path, mode="salt")
    stride = 24 + int.from_bytes(data[8:12], "big")
    offsets = list(range(32, len(data), stride))
    commits = [
        i
        for i, offset in enumerate(offsets)
        if int.from_bytes(data[offset + 4 : offset + 8], "big")
    ]
    assert len(commits) >= 3, "Fixture needs separate acknowledged WAL transactions"
    frame = 0 if position == "first" else commits[0] + 1
    offset = offsets[frame] + 8 + salt_byte
    damaged = data[:offset] + bytes([data[offset] ^ 1]) + data[offset + 1 :]
    wal.write_bytes(damaged)
    try:
        recovered = OperatorStore.open(
            service.store.settings, initialize=False, clock=clock
        )
    except OperatorError as error:
        assert error.code == "store_corrupt" and not error.retryable
        assert wal.read_bytes() == damaged
    else:
        try:
            assert_acknowledged_receipts(recovered, expected)
        finally:
            recovered.close()


@pytest.mark.parametrize("resets", [[4], [4, 2, 1], [6, 3, 1, 1]])
def test_checkpoint_reused_wal_preserves_all_acknowledged_receipts(
    service, record_data, tmp_path, clock, resets
):
    _, data, expected = crashed_wal(
        service, record_data, tmp_path, mode="reuse", resets=resets
    )
    stride = 24 + int.from_bytes(data[8:12], "big")
    salts = {data[offset + 8 : offset + 16] for offset in range(32, len(data), stride)}
    assert data[16:24] in salts
    assert len(salts) >= (
        2 if len(resets) == 1 else 3
    ), "Fixture needs actual retained older generations"
    recovered = OperatorStore.open(
        service.store.settings, initialize=False, clock=clock
    )
    try:
        assert_acknowledged_receipts(recovered, expected)
    finally:
        recovered.close()


@pytest.mark.parametrize(
    "damage", ["checksum", "return_to_active", "same_age_new_salt"]
)
def test_entire_old_tail_is_checked(service, record_data, tmp_path, clock, damage):
    wal, data, _ = crashed_wal(
        service, record_data, tmp_path, mode="reuse", resets=[4, 2, 1]
    )
    stride = 24 + int.from_bytes(data[8:12], "big")
    offsets = list(range(32, len(data), stride))
    first_tail = next(
        i
        for i, offset in enumerate(offsets)
        if data[offset + 8 : offset + 16] != data[16:24]
    )
    offset = offsets[first_tail + 1]
    previous = offsets[first_tail]
    assert data[offset + 8 : offset + 16] == data[previous + 8 : previous + 16]
    damaged = bytearray(data)
    if damage == "checksum":
        damaged[offset + 24] ^= 1
    elif damage == "return_to_active":
        damaged[offset + 8 : offset + 16] = data[16:24]
    else:
        damaged[offset + 12] ^= 1
    wal.write_bytes(damaged)
    with pytest.raises(OperatorError, match="store_corrupt"):
        OperatorStore.open(service.store.settings, initialize=False, clock=clock)
    assert wal.read_bytes() == damaged
