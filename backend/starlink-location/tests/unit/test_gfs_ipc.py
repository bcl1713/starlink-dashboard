"""Readers and scientific owners coordinate through real persistent file locks."""

import subprocess
import sys
import uuid
from contextlib import contextmanager

import pytest
from app.services.aviation_weather.settings import AviationSettingsStore

from tests.fixtures.gfs_fields import RUN


@contextmanager
def other_owner(path):
    command = [
        sys.executable,
        "-c",
        "import fcntl,sys; f=open(sys.argv[1],'a'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); sys.stdin.read()",
        str(path),
    ]
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    try:
        import select

        assert select.select([process.stdout], [], [], 5)[0]
        assert process.stdout.readline().strip() == "ready"
        yield process
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        process.stdout.close()


def mailbox(tmp_path):
    from app.services.aviation_weather.gfs.ipc import GfsMailbox

    settings = AviationSettingsStore(tmp_path / "settings.json")
    enabled = settings.update({"winds": True})
    return GfsMailbox(tmp_path / "mailbox", settings), settings, enabled


def test_reader_expiry_revision_and_sibling_disconnect(tmp_path):
    box, settings, enabled = mailbox(tmp_path)
    first, second = uuid.uuid4().hex, uuid.uuid4().hex
    box.renew(first, enabled, RUN)
    box.renew(second, enabled, RUN + 10000)
    box.withdraw(first)
    assert box.current(RUN + 119999) == enabled
    assert box.current(RUN + 130000) is None
    changed = settings.update(
        {"gfs_selection": {"pressure_pa": 30000, "horizon_hours": 3}}
    )
    box.invalidate(changed.revision)
    with pytest.raises(ValueError):
        box.renew(first, enabled, RUN + 20000)
    box.renew(second, changed, RUN + 20000)
    box.withdraw(first)  # old API shutdown cannot revoke replacement owner.
    assert box.current(RUN + 20001) == changed


def test_missing_heartbeat_does_not_prove_worker_absence(tmp_path):
    box, _settings, enabled = mailbox(tmp_path)
    with other_owner(box.root / "worker.lock"):
        assert not box.acknowledged(enabled.revision)
        assert not box.healthy(RUN)
        box.heartbeat(enabled.revision, uuid.uuid4().hex, RUN)
        assert box.acknowledged(enabled.revision)
        assert box.healthy(RUN + 15000)
        assert not box.healthy(RUN + 15001)
        box.invalidate(enabled.revision + 1)
        assert not box.acknowledged(enabled.revision + 1)
    assert box.acknowledged(enabled.revision + 1)
    assert not box.healthy(RUN)


def test_backward_clock_invalidates_demand_and_cannot_renew_it(tmp_path):
    box, _settings, enabled = mailbox(tmp_path)
    owner = uuid.uuid4().hex
    box.renew(owner, enabled, RUN)
    assert box.current(RUN - 1) is None
    with pytest.raises(ValueError):
        box.renew(owner, enabled, RUN - 1)
    assert box.current(RUN) is None


def test_reader_admission_is_bounded_to_sixteen_owners(tmp_path):
    box, _settings, enabled = mailbox(tmp_path)
    for _ in range(16):
        box.renew(uuid.uuid4().hex, enabled, RUN)
    with pytest.raises(ValueError):
        box.renew(uuid.uuid4().hex, enabled, RUN)


def test_worker_reads_atomic_settings_without_writing_a_settings_lock(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"winds":true,"revision":1}')
    reader = AviationSettingsStore(path, readonly=True)
    assert reader.get().winds
    assert not path.with_suffix(".json.lock").exists()
    with pytest.raises(RuntimeError):
        reader.update({"winds": False})


def test_reader_has_a_monotonic_deadline_when_utc_stops_advancing(tmp_path):
    from app.services.aviation_weather.gfs.ipc import GfsMailbox

    box, settings, enabled = mailbox(tmp_path)
    elapsed = [0.0]
    worker_view = GfsMailbox(box.root, settings, monotonic=lambda: elapsed[0])
    box.renew(uuid.uuid4().hex, enabled, RUN)
    assert worker_view.current(RUN) == enabled
    elapsed[0] = 120.0
    assert worker_view.current(RUN) is None


def test_old_worker_heartbeat_cannot_authorize_a_replacement_owner(tmp_path):
    from app.services.aviation_weather.gfs.store import atomic_json

    box, _settings, enabled = mailbox(tmp_path)
    first, second = uuid.uuid4().hex, uuid.uuid4().hex
    with other_owner(box.root / "worker.lock"):
        box.heartbeat(enabled.revision, first, RUN)
        atomic_json(box.root / "worker.json", {"owner": second})
        assert not box.healthy(RUN)
        assert not box.acknowledged(enabled.revision)
