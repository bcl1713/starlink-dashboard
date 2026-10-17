"""Writers serialize version checks; committed retries precede mission access."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.mission import storage
from app.operator.errors import OperatorError
from tests.operator.service_helpers import create, submit, update


def test_same_version_and_receipt_retry(service, record_data):
    saved = create(service, record_data)
    commands = [update(service, saved, audit_note=note) for note in ("first", "second")]
    keys = [str(uuid4()), str(uuid4())]
    barrier = Barrier(2)

    def write(i):
        barrier.wait(timeout=5)
        try:
            return submit(service, commands[i], keys[i])
        except OperatorError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, range(2)))
    success = next(i for i, r in enumerate(results) if not isinstance(r, OperatorError))
    assert results[1 - success].code == "version_conflict"
    assert results[1 - success].current_version == 2
    newer = submit(service, update(service, results[success].saved_records[0]))
    storage.get_mission_file_path("demo-mission").unlink()
    assert submit(service, commands[success], keys[success]) == results[success]
    with pytest.raises(OperatorError) as conflict:
        submit(service, commands[1 - success], keys[success])
    assert conflict.value.code == "idempotency_conflict"
    with pytest.raises(OperatorError) as epoch:
        service.execute(commands[success], key=keys[success], epoch=str(uuid4()))
    assert epoch.value.code == "store_epoch_changed"
    assert [r.version for r in service.history(str(saved.record_id)).items] == [1, 2, 3]
    assert service.get(str(saved.record_id)) == newer.saved_records[0]
