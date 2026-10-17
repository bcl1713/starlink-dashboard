"""Record, bound, kill and reap only explicitly owned fault workers."""

import json
import os
import select
import signal
import subprocess
import sys
from contextlib import contextmanager


@contextmanager
def stopped_worker(tmp_path, config):
    configuration = tmp_path / "worker.json"
    configuration.write_text(json.dumps(config))
    read_fd, write_fd = os.pipe()
    command = [
        sys.executable,
        "-m",
        "tests.operator.crash_worker",
        str(configuration),
        str(write_fd),
    ]
    ownership = tmp_path / "worker-ownership.json"
    state = {"command": command, "paths": [str(configuration)], "state": "starting"}
    ownership.write_text(json.dumps(state))
    worker = None
    try:
        with (tmp_path / "worker.log").open("w") as log:
            worker = subprocess.Popen(
                command,
                pass_fds=(write_fd,),
                start_new_session=True,
                stdout=log,
                stderr=log,
            )
            os.close(write_fd)
            write_fd = None
            state.update(pid=worker.pid, pgid=worker.pid, state="running")
            ownership.write_text(json.dumps(state))
            assert select.select([read_fd], [], [], 15)[
                0
            ], "Fault worker did not reach its barrier"
            event = json.loads(os.read(read_fd, 65536))
            yield worker, event
    finally:
        if worker:
            if worker.poll() is None:
                worker.terminate()
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(timeout=5)
            state.update(state="reaped", exit_code=worker.returncode)
            try:
                os.killpg(worker.pid, 0)
            except ProcessLookupError:
                state["process_group_remaining"] = False
            else:
                state["process_group_remaining"] = True
            ownership.write_text(json.dumps(state))
            assert not state["process_group_remaining"]
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
