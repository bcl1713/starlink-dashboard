"""Byte-preserving loopback transport into offline rootless Docker Nginx."""

import argparse
import os
import selectors
import signal
import socketserver
import subprocess
import threading
import time


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        child = subprocess.Popen(
            self.server.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        with self.server.lock:
            self.server.children.add(child)
        self.request.settimeout(10)
        try:
            deadline = time.monotonic() + 120
            with selectors.DefaultSelector() as selected:
                selected.register(self.request, selectors.EVENT_READ, "browser")
                selected.register(child.stdout, selectors.EVENT_READ, "nginx")
                while time.monotonic() < deadline:
                    for key, _ in selected.select(timeout=1):
                        data = os.read(key.fd, 65536)
                        if not data:
                            return
                        if key.data == "browser":
                            child.stdin.write(data)
                            child.stdin.flush()
                        else:
                            self.request.sendall(data)
                    if child.poll() is not None:
                        return
        except (BrokenPipeError, ConnectionError, TimeoutError, OSError):
            return
        finally:
            child.stdin.close()
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()
            with self.server.lock:
                self.server.children.discard(child)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, command):
        self.command = command
        self.children = set()
        self.lock = threading.Lock()
        super().__init__(address, Handler)

    def server_close(self):
        super().server_close()
        with self.lock:
            children = list(self.children)
        for child in children:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command

    def stop(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with Server(("127.0.0.1", args.port), command) as server:
        server.serve_forever()
