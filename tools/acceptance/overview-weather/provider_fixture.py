"""Only provider DNS/TLS I/O is synthetic; HTTP validation remains production."""

import asyncio
import json
import math
import os
import ssl
import struct
import time
import uuid
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


def tile_png(x, y, *, coverage=False, z=2, detail=False):
    # Independently specified XYZ rows distinguish Mercator from latitude-linear
    # sampling, and columns distinguish the prime-meridian/antimeridian edges.
    colors = [
        [(255, 40, 40), (255, 160, 40), (255, 40, 255), (160, 40, 255)],
        [(255, 40, 40), (40, 40, 255), (255, 40, 40), (255, 255, 40)],
        [(255, 40, 40), (255, 255, 40), (40, 255, 40), (40, 255, 255)],
        [(255, 40, 40), (160, 40, 255), (40, 255, 255), (40, 40, 255)],
    ]
    scale = 2 ** (z - 2)
    color = (
        [0, 0, 0, 255 if x // scale == 0 else 0]
        if coverage
        else [*colors[y // scale][x // scale], 220]
    )

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = (b"\0" + bytes(color) * 512) * 512
    if detail and z > 2:
        lines = []
        for row in range(512):
            latitude = math.degrees(
                math.atan(math.sinh(math.pi * (1 - 2 * (y + (row + 0.5) / 512) / 2**z)))
            )
            line = bytearray(b"\0")
            for col in range(512):
                longitude = (x + (col + 0.5) / 512) / 2**z * 360 - 180
                value = color
                if coverage and -78 < longitude < -74 and 33.8 < latitude < 38:
                    value = [0, 0, 0, 255]
                elif not coverage and -78 < longitude < -74 and 31 < latitude < 35:
                    value = [20, 255, 20, 255]
                line.extend(value)
            lines.append(bytes(line))
        rows = b"".join(lines)
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
        self.stream_id = uuid.uuid4().hex
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
        event("request", path=path, host=self.host, stream_id=self.stream_id)
        await asyncio.sleep(float(settings.get("delay", 0)))
        status = 503 if settings.get("fail") else 200
        frame = settings.get("frame", int(time.time()) // 60 * 60 - 120)
        radar_path = settings.get("radar_path", f"/v2/radar/frame_{frame:x}")
        if self.host == "api.rainviewer.com":
            body = json.dumps(
                {
                    "version": "2.0",
                    "generated": int(time.time()),
                    "host": "https://tilecache.rainviewer.com",
                    "radar": {
                        "past": [{"time": frame, "path": radar_path}],
                        "nowcast": [],
                    },
                    "satellite": {"infrared": []},
                }
            ).encode()
            content_type = "application/json"
        else:
            parts = path.split("/")
            if "/radar/" in path and not path.startswith(radar_path + "/512/"):
                status = 404
            z, x, y = map(int, parts[5:8])
            if settings.get("detail_fail") and z > 2:
                status = 503
            body = tile_png(
                x,
                y,
                z=z,
                coverage="coverage" in path,
                detail=settings.get("detail_fixture", False),
            )
            if settings.get("capture_identity"):
                capture = json.loads(Path("/capture/capture.json").read_text())
                pairs = capture["tiles"][settings["capture_identity"]]
                match = next(
                    (
                        entry
                        for entry in pairs
                        if entry["key"] == {"z": z, "x": x, "y": y}
                    ),
                    None,
                )
                if match:
                    field = "absence_path" if "coverage" in path else "radar_path"
                    tile = Path("/capture") / match["pair"][field]
                    import hashlib

                    expected = match["pair"][
                        "absence_sha256" if "coverage" in path else "radar_sha256"
                    ]
                    body = tile.read_bytes()
                    if hashlib.sha256(body).hexdigest() != expected:
                        raise ValueError("Capture hash changed")
                else:
                    status = 503
            event("response", path=path, status=status, stream_id=self.stream_id)
            content_type = "image/png"
        wire = (
            f"HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nRetry-After: 30\r\nConnection: close\r\n\r\n"
        ).encode() + body
        self.reader.feed_data(wire)
        self.reader.feed_eof()

    def close(self):
        self.closed += 1
        event("close", path=self.path, count=self.closed, stream_id=self.stream_id)

    async def wait_closed(self):
        self.waited += 1
        event(
            "wait_closed", path=self.path, count=self.waited, stream_id=self.stream_id
        )


async def open_tls(ip, host, context, timeout):
    assert (
        ip == "1.1.1.1"
        and context.check_hostname
        and context.verify_mode == ssl.CERT_REQUIRED
    )
    reader = asyncio.StreamReader()
    writer = Writer(reader, host)
    event("dial", host=host, ip=ip, verified=True, stream_id=writer.stream_id)
    return reader, writer
