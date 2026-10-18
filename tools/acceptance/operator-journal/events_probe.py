"""Production-image acknowledgment durability and unchanged export controls."""

import json
import os
import select
import signal
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def run(owner, origin, evidence_root):
    result = json.loads(
        owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "/acceptance/events_probe.py",
            timeout=120,
        ).splitlines()[-1]
    )
    (Path(evidence_root) / "events-backend.json").write_text(
        json.dumps(result, indent=2)
    )
    return result


@contextmanager
def opened(root):
    from app.mission import storage
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings
    from scenario import ScenarioClock
    from seed import seed_demo

    clock = ScenarioClock()
    seeded = seed_demo(root, clock=clock, mode="simulation")
    previous = storage.MISSIONS_DIR
    storage.MISSIONS_DIR = Path(root) / "missions"
    runtime = OperatorRuntime.start(
        OperatorSettings(
            enabled=True,
            root=Path(root) / "operator",
            source_mode="simulation",
            simulation_run_id=seeded["run_id"],
        ),
        clock=clock,
    )
    try:
        assert runtime.service is not None
        yield runtime, clock
    finally:
        runtime.close()
        storage.MISSIONS_DIR = previous


def pending(runtime, clock):
    from app.operator.event_feed import build_snapshot
    from app.operator.event_models import AckRequest
    from app.operator.event_sources import EventSourceAdapter
    from app.operator.models import CreateRecord
    from datetime import timedelta

    command = CreateRecord(
        record_type="call",
        mission_id="synthetic-mission-a",
        scope="mission",
        time={"planned_start_at": clock.now() + timedelta(minutes=12)},
        payload={
            "entry_type": "call",
            "title": "Synthetic durable requirement",
            "status": "scheduled",
            "prep_lead_minutes": 10,
        },
    )
    service = runtime.service
    record = service.execute(
        command, key=str(uuid4()), epoch=str(runtime.health().api_epoch)
    ).saved_records[0]
    snapshot = build_snapshot(
        runtime, "synthetic-mission-a", EventSourceAdapter(service)
    )
    event = next(
        e
        for e in snapshot.events
        if e.kind == "call_prep" and e.source_ref == str(record.record_id)
    )
    return (
        AckRequest(
            occurrence_id=event.notification.generation,
            severity_generation=event.notification.severity_generation,
            snapshot_token=snapshot.snapshot_token,
        ),
        event,
    )


def crash_ack(root, *, after):
    from app.operator.event_ack import acknowledge
    from app.operator.errors import OperatorError
    from app.operator.recovery import verify_store
    from app.operator.runtime import OperatorRuntime

    with opened(root) as (runtime, clock):
        request, _ = pending(runtime, clock)
        key, epoch = str(uuid4()), str(runtime.health().api_epoch)
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            try:
                os.setsid()
                (Path(root) / "crash-owner.json").write_text(
                    json.dumps(
                        {
                            "pid": os.getpid(),
                            "pgid": os.getpgrp(),
                            "barrier": "after" if after else "before",
                        }
                    )
                )
                original = runtime.service.store._connection

                class CommitBarrier:
                    def __init__(self, connection):
                        self.connection = connection

                    def __getattr__(self, name):
                        return getattr(self.connection, name)

                    def commit(self):
                        writes = self.connection.total_changes > 0
                        if writes and not after:
                            os.write(write_fd, b"ready")
                            signal.pause()
                        self.connection.commit()
                        if writes and after:
                            os.write(write_fd, b"ready")
                            signal.pause()

                runtime.service.store._connection = lambda: CommitBarrier(original())
                acknowledge(request, key=key, epoch=epoch, runtime=runtime)
                os._exit(3)
            except BaseException:
                os.write(write_fd, b"failed")
                os._exit(4)
        os.close(write_fd)
        reaped = False
        try:
            assert select.select([read_fd], [], [], 8)[
                0
            ], "Synthetic commit barrier did not arrive"
            assert os.read(read_fd, 64) == b"ready"
            assert os.getpgid(pid) == pid
            os.killpg(pid, signal.SIGKILL)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = os.waitpid(pid, os.WNOHANG)
                if result[0]:
                    reaped = True
                    break
                time.sleep(0.01)
            assert reaped, "Synthetic commit worker did not reap"
            runtime.close()
            restarted = OperatorRuntime.start(runtime.settings, clock=clock)
            try:
                assert restarted.service is not None
                assert verify_store(restarted.service.store).ready
                with restarted.service.store.connect() as db:
                    count = db.execute(
                        "SELECT count(*) FROM event_acknowledgments"
                    ).fetchone()[0]
                assert count == int(after)
                if after:
                    receipt, replayed = acknowledge(
                        request, key=key, epoch=epoch, runtime=restarted
                    )
                    assert replayed and receipt.occurrence_id == request.occurrence_id
                else:
                    try:
                        acknowledge(request, key=key, epoch=epoch, runtime=restarted)
                        raise AssertionError(
                            "Uncommitted old token was accepted after restart"
                        )
                    except OperatorError as error:
                        assert error.code == "event_snapshot_changed"
                (Path(root) / "crash-owner.json").write_text(
                    json.dumps({"pid": pid, "reaped": True, "groupRemaining": False})
                )
            finally:
                restarted.close()
        finally:
            os.close(read_fd)
            if not reaped:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
    return True


def probe(root):
    from app.operator.event_ack import acknowledge
    from app.operator.event_feed import build_snapshot
    from app.operator.event_sources import EventSourceAdapter
    from app.operator.projections import capture_projection
    from app.operator.backup import backup_store
    from app.operator.recovery import restore_store, verify_store
    from app.operator.runtime import OperatorRuntime

    root = Path(root)
    with opened(root / "durable") as (runtime, clock):
        request, event = pending(runtime, clock)
        service = runtime.service
        before = dict(
            capture_projection(
                service.store, mission_id="synthetic-mission-a", include_audit=True
            ).files
        )
        epoch = str(runtime.health().api_epoch)
        key = str(uuid4())
        receipt, replayed = acknowledge(request, key=key, epoch=epoch, runtime=runtime)
        assert not replayed
        assert acknowledge(request, key=key, epoch=epoch, runtime=runtime)[1]
        duplicate, _ = acknowledge(
            request, key=str(uuid4()), epoch=epoch, runtime=runtime
        )
        assert duplicate.acknowledgment_id == receipt.acknowledgment_id
        with service.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM event_acknowledgments"
            ).fetchone() == (1,)
        assert (
            dict(
                capture_projection(
                    service.store, mission_id="synthetic-mission-a", include_audit=True
                ).files
            )
            == before
        )
        assert verify_store(service.store).ready
        manifest = backup_store(service.store, directory=root / "backups")
        health = restore_store(runtime.settings, manifest=manifest, clock=clock)
        assert health.ready and str(health.api_epoch) != epoch
        runtime.close()
        restored = OperatorRuntime.start(runtime.settings, clock=clock)
        try:
            snapshot = build_snapshot(
                restored, "synthetic-mission-a", EventSourceAdapter(restored.service)
            )
            assert next(
                e
                for e in snapshot.events
                if e.notification.generation == request.occurrence_id
            ).notification.acknowledged
        finally:
            restored.close()
        example = {
            "event": event.model_dump(mode="json"),
            "acknowledgment": receipt.model_dump(mode="json"),
        }
    before_crash = crash_ack(root / "commit-before", after=False)
    after_crash = crash_ack(root / "commit-after", after=True)
    return {
        "synthetic": True,
        "oneDurableAcknowledgment": True,
        "operationsUnchanged": True,
        "backupRestore": True,
        "commitCrashBefore": before_crash,
        "commitCrashAfter": after_crash,
        "example": example,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            probe(
                Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
                / "operator"
                / "event-durability-probe"
            )
        )
    )
