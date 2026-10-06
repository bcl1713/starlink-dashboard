"""An absolute deadline owns the entire urllib exchange in a reapable worker."""

import ctypes
import json
import os
import selectors
import signal
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect refused; capture an explicit approved URL")


class Response:
    def __init__(self, child, selector, deadline):
        self.child, self.selector, self.deadline = child, selector, deadline
        self.buffer = b""

    def read(self, size):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("capture deadline")
        if self.buffer:
            value, self.buffer = self.buffer[:size], self.buffer[size:]
            return value
        if not self.selector.select(remaining):
            raise TimeoutError("capture deadline")
        value = os.read(self.child.stdout.fileno(), size)
        if time.monotonic() >= self.deadline:
            raise TimeoutError("capture deadline")
        if not value:
            remaining = self.deadline - time.monotonic()
            try:
                result = self.child.wait(timeout=max(0, remaining))
            except subprocess.TimeoutExpired as error:
                raise TimeoutError("capture deadline") from error
            if result:
                raise ConnectionError("capture worker failed during transfer")
        return value

    def metadata(self):
        data = b""
        while b"\n" not in data:
            data += self.read(4096)
            if not data or len(data) > 16384:
                raise ConnectionError("invalid capture worker response")
        header, self.buffer = data.split(b"\n", 1)
        return json.loads(header)


@contextmanager
def open_exchange(url, *, timeout=45, command=None, record=lambda **values: None):
    command = command or [
        sys.executable,
        str(Path(__file__).resolve()),
        url,
        str(os.getpid()),
    ]
    deadline = time.monotonic() + timeout
    record(event="exchange_intent", command=command)
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        record(event="exchange_owner", pid=child.pid, process_group=child.pid)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            response = Response(child, selector, deadline)
            metadata = response.metadata()
            if metadata.get("error") == "http":
                raise HTTPError(
                    url,
                    metadata["status"],
                    "capture HTTP failure",
                    {"Retry-After": metadata.get("retry_after", "1")},
                    None,
                )
            if metadata.get("status") != 200:
                raise ConnectionError("capture worker could not open response")
            yield response
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=1)
        child.stdout.close()
        record(event="exchange_closed", pid=child.pid, result=child.returncode)


def arm_parent_death(parent_pid):
    # Linux ensures a killed capture cannot leave a separate-session socket owner.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0):
        raise RuntimeError("capture parent-death setup failed")
    if os.getppid() != parent_pid:
        raise SystemExit(1)


def worker(url):
    opened = False
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            url, timeout=45
        ) as response:
            print(json.dumps({"status": response.status}), flush=True)
            opened = True
            while chunk := response.read(64 * 1024):
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
    except HTTPError as error:
        print(
            json.dumps(
                {
                    "error": "http",
                    "status": error.code,
                    "retry_after": error.headers.get("Retry-After", "1"),
                }
            ),
            flush=True,
        )
    except (OSError, ValueError):
        if not opened:
            print(json.dumps({"error": "open"}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    arm_parent_death(int(sys.argv[2]))
    raise SystemExit(worker(sys.argv[1]))
