"""Allowlisted HTTPS streaming in deadline-owned, parent-death-aware workers."""

import ctypes
import fcntl
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

MAX_BYTES = 32 * 1024 * 1024
HOSTS = {
    "noaa-gfs-bdp-pds.s3.amazonaws.com",
    "noaa-goes19.s3.amazonaws.com",
    "aviationweather.gov",
}
USER_AGENT = "starlink-dashboard/issue-290-aviation-proof (bounded research capture)"


def validate_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("capture requires an allowlisted HTTPS URL")


class ExchangeBudget:
    """Cross-process admission: two leases, 20 starts/60s, 5 GiB/day reserved."""

    def __init__(self, root=None):
        self.root = Path(
            root
            or Path(tempfile.gettempdir()) / f"aviation-proof-admission-{os.getuid()}"
        )

    @contextmanager
    def acquire(self):
        self.root.mkdir(parents=True, exist_ok=True)
        token = f"{os.getpid()}-{time.monotonic_ns()}"

        def update(add):
            with (self.root / "lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                path = self.root / "state.json"
                state = (
                    json.loads(path.read_text())
                    if path.exists()
                    else {"attempts": [], "leases": {}, "daily": []}
                )
                now = time.time()
                state["attempts"] = [t for t in state["attempts"] if now - t < 60]
                state["daily"] = [t for t in state["daily"] if now - t < 86400]
                for key, pid in list(state["leases"].items()):
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        del state["leases"][key]
                if add:
                    if len(state["leases"]) >= 2:
                        raise ValueError("two exchanges already active")
                    if len(state["attempts"]) >= 20:
                        raise ValueError("20 attempts per 60 seconds exceeded")
                    if (len(state["daily"]) + 1) * MAX_BYTES > 5 * 1024**3:
                        raise ValueError("5 GiB/day reservation exhausted")
                    state["leases"][token] = os.getpid()
                    state["attempts"].append(now)
                    state["daily"].append(now)
                else:
                    state["leases"].pop(token, None)
                temporary = path.with_suffix(".partial")
                temporary.write_text(json.dumps(state))
                temporary.replace(path)

        update(True)
        try:
            yield
        finally:
            update(False)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("redirect refused")


class Response:
    def __init__(self, child, selector, deadline):
        self.child = child
        self.selector = selector
        self.deadline = deadline
        self.buffer = b""

    def read(self, size):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("30-second absolute HTTP deadline")
        if self.buffer:
            value, self.buffer = self.buffer[:size], self.buffer[size:]
            return value
        if not self.selector.select(left):
            raise TimeoutError("absolute HTTP deadline")
        value = os.read(self.child.stdout.fileno(), size)
        if time.monotonic() >= self.deadline:
            raise TimeoutError("absolute HTTP deadline")
        if not value:
            try:
                code = self.child.wait(timeout=max(0, self.deadline - time.monotonic()))
            except subprocess.TimeoutExpired as error:
                raise TimeoutError("absolute HTTP deadline") from error
            if code:
                raise ConnectionError("exchange worker failed")
        return value

    def metadata(self):
        value = b""
        while b"\n" not in value:
            chunk = self.read(4096)
            if not chunk or len(value) + len(chunk) > 16384:
                raise ValueError("invalid worker metadata")
            value += chunk
        line, self.buffer = value.split(b"\n", 1)
        return json.loads(line)


def reap(child):
    # The transport never launches grandchildren. Signal exact owned session.
    for sig, grace in ((signal.SIGTERM, 0.5), (signal.SIGKILL, 1)):
        if child.poll() is not None:
            break
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            break
        try:
            child.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            continue
    child.wait(timeout=1)
    child.stdout.close()


@contextmanager
def open_exchange(
    url,
    *,
    byte_range=None,
    timeout=30,
    command=None,
    record=lambda **x: None,
    budget=None,
):
    validate_url(url)
    if not 0 < timeout <= 30:
        raise ValueError("HTTP deadline must be at most 30 seconds")
    if byte_range is not None and (
        len(byte_range) != 2
        or any(type(n) is not int for n in byte_range)
        or not 0 <= byte_range[0] <= byte_range[1]
        or byte_range[1] - byte_range[0] + 1 > MAX_BYTES
    ):
        raise ValueError("invalid byte range")
    cmd = command or [
        sys.executable,
        str(Path(__file__).resolve()),
        url,
        str(os.getpid()),
        json.dumps(byte_range),
    ]
    with (budget or ExchangeBudget()).acquire():
        deadline = time.monotonic() + timeout
        record(
            event="exchange_intent",
            command=cmd,
            parent_pid=os.getpid(),
            deadline_seconds=timeout,
        )
        child = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            record(event="exchange_owner", pid=child.pid, process_group=child.pid)
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                response = Response(child, selector, deadline)
                meta = response.metadata()
                headers = meta.get("headers", {})
                record(
                    event="exchange_response",
                    url=url,
                    byte_range=byte_range,
                    status=meta.get("status"),
                    headers={
                        key: headers[key]
                        for key in (
                            "content-length",
                            "content-range",
                            "etag",
                            "last-modified",
                            "content-type",
                        )
                        if key in headers
                    },
                )
                expected = 206 if byte_range else 200
                if meta.get("status") != expected:
                    raise ValueError(
                        f"expected HTTP {expected}, received {meta.get('status')}"
                    )
                length = headers.get("content-length")
                response.length = int(length) if length is not None else None
                if (
                    response.length is not None
                    and not 0 <= response.length <= MAX_BYTES
                ):
                    raise ValueError("object exceeds 32 MiB")
                if headers.get("content-encoding", "identity") != "identity":
                    raise ValueError("encoded response refused")
                if byte_range:
                    start, end = byte_range
                    range_match = re.fullmatch(
                        r"bytes (\d+)-(\d+)/(\d+)", headers.get("content-range", "")
                    )
                    if (
                        not range_match
                        or tuple(map(int, range_match.groups()[:2])) != (start, end)
                        or int(range_match[3]) <= end
                    ):
                        raise ValueError("Content-Range mismatch")
                    if response.length != end - start + 1:
                        raise ValueError("range length mismatch")
                yield response
        finally:
            reap(child)
            record(event="exchange_closed", pid=child.pid, result=child.returncode)


def worker(url, parent, byte_range):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0):
        raise RuntimeError("parent-death setup failed")
    if os.getppid() != parent:
        return 1
    validate_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if byte_range is not None:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            print(
                json.dumps(
                    {
                        "status": response.status,
                        "headers": {k.lower(): v for k, v in response.headers.items()},
                    }
                ),
                flush=True,
            )
            while chunk := response.read(65536):
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(worker(sys.argv[1], int(sys.argv[2]), json.loads(sys.argv[3])))
