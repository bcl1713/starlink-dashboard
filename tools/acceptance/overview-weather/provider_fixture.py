"""Only provider DNS/TLS I/O is synthetic; HTTP validation remains production."""

import asyncio
import json
import os
import ssl
import struct
import time
import zlib
from pathlib import Path

CONTROL = Path(
    os.environ.get("WEATHER_ACCEPTANCE_CONTROL_PATH", "/control/control.json")
)
EVENTS = CONTROL.with_name("events.jsonl")


def control():
    return json.loads(CONTROL.read_text())


def event(kind, **values):
    with EVENTS.open("a") as output:
        output.write(json.dumps({"event": kind, "at": time.time(), **values}) + "\n")


def tile_png(x, y, *, coverage=False):
    # Independently specified XYZ rows distinguish Mercator from latitude-linear
    # sampling, and columns distinguish the prime-meridian/antimeridian edges.
    colors = [
        [(80, 80, 80), (255, 160, 40), (255, 40, 255), (160, 40, 255)],
        [(80, 80, 80), (40, 40, 255), (255, 40, 40), (255, 255, 40)],
        [(80, 80, 80), (255, 255, 40), (40, 255, 40), (40, 255, 255)],
        [(80, 80, 80), (160, 40, 255), (40, 255, 255), (40, 40, 255)],
    ]
    color = [0, 0, 0, 255 if x == 0 else 0] if coverage else [*colors[y][x], 220]

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = (b"\0" + bytes(color) * 512) * 512
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 512, 512, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


async def resolve(host, timeout):
    assert host in {"api.rainviewer.com", "tilecache.rainviewer.com"}
    return ["1.1.1.1"]


class Writer:
    def __init__(self, reader, host):
        self.reader, self.host = reader, host
        self.request = b""
        self.path = None
        self.closed = 0
        self.waited = 0

    def write(self, data):
        self.request += data

    async def drain(self):
        path = self.request.decode().split(" ")[1]
        self.path = path
        settings = control()
        event("request", path=path, host=self.host)
        await asyncio.sleep(float(settings.get("delay", 0)))
        status = 503 if settings.get("fail") else 200
        if self.host == "api.rainviewer.com":
            frame = settings.get("frame", int(time.time()) // 60 * 60 - 120)
            body = json.dumps(
                {
                    "host": "https://tilecache.rainviewer.com",
                    "radar": {"past": [{"time": frame, "path": f"/v2/radar/{frame}"}]},
                }
            ).encode()
            content_type = "application/json"
        else:
            parts = path.split("/")
            body = tile_png(int(parts[6]), int(parts[7]), coverage="coverage" in path)
            content_type = "image/png"
        wire = (
            f"HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nRetry-After: 30\r\nConnection: close\r\n\r\n"
        ).encode() + body
        self.reader.feed_data(wire)
        self.reader.feed_eof()

    def close(self):
        self.closed += 1
        event("close", path=self.path, count=self.closed)

    async def wait_closed(self):
        self.waited += 1
        event("wait_closed", path=self.path, count=self.waited)


async def open_tls(ip, host, context, timeout):
    assert (
        ip == "1.1.1.1"
        and context.check_hostname
        and context.verify_mode == ssl.CERT_REQUIRED
    )
    event("dial", host=host, ip=ip, verified=True)
    reader = asyncio.StreamReader()
    return reader, Writer(reader, host)
