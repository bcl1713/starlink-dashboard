"""Pinned source-shaped HTTP only; actual quotas, IPC, decoder and publication."""

import asyncio
import hashlib
import json
import logging
import signal
import time
from pathlib import Path

import httpx
from app.services.aviation_weather.gfs.ipc import GfsMailbox
from app.services.aviation_weather.gfs.quota import GfsQuota
from app.services.aviation_weather.gfs.store import GfsProductStore
from app.services.aviation_weather.gfs.transport import GfsTransport
from app.services.aviation_weather.gfs.worker import GfsWorker
from app.services.aviation_weather.settings import AviationSettingsStore

CONTROL = Path("/control/control.json")
CAPTURE = Path("/capture/gfs")
KEY = "gfs.20261006/00/atmos/gfs.t00z.pgrb2.0p25.f006"
ETAG = '"7a8c1bb19de384dc3052fae6aeee2efc"'
SIZE = 539601570
_anchor = None


def control():
    return json.loads(CONTROL.read_bytes())


def clock():
    global _anchor
    values = control()
    epoch = values.get("replay_utc_ms")
    if epoch is None:
        return time.time()
    if "replay_monotonic" in values:
        return epoch / 1000 + time.monotonic() - values["replay_monotonic"]
    if _anchor is None or _anchor[0] != epoch:
        _anchor = epoch, time.monotonic()
    return epoch / 1000 + time.monotonic() - _anchor[1]


def event(value):
    with Path("/control/gfs-events.jsonl").open("a") as stream:
        stream.write(json.dumps(value) + "\n")


class SourceFixture:
    def __init__(self):
        capture = (
            Path("/capture/gfs-presentation")
            if control().get("gfs_presentation")
            else CAPTURE
        )
        manifest = json.loads((capture / "manifest.json").read_bytes())
        self.runs = {}
        if "runs" in manifest:
            for run in manifest["runs"]:
                index = (capture / run["index"]).read_bytes()
                if hashlib.sha256(index).hexdigest() != run["index_sha256"]:
                    raise ValueError("Pinned index drift")
                self.runs[run["key"]] = {**run, "index_bytes": index, "ranges": {}}
        else:
            self.runs[KEY] = {
                "etag": ETAG,
                "size": SIZE,
                "index_bytes": (capture / "source.idx").read_bytes(),
                "ranges": {},
            }
        for item in manifest["objects"]:
            body = (capture / item["filename"]).read_bytes()
            if hashlib.sha256(body).hexdigest() != item["sha256"]:
                raise ValueError("Pinned source drift")
            if item.get("range"):
                self.runs[item.get("key", KEY)]["ranges"][
                    f"bytes={item['range'][0]}-{item['range'][1]}"
                ] = body

    def __call__(self, request):
        assert request.url.host == "noaa-gfs-bdp-pds.s3.amazonaws.com"
        key = request.url.path.lstrip("/")
        status, headers, body = 200, {}, b""
        if not key:
            prefix = request.url.params["prefix"]
            entries = ""
            if prefix == "gfs.20261006/":
                entries = (
                    "<CommonPrefixes><Prefix>gfs.20261006/00/</Prefix></CommonPrefixes>"
                )
            elif prefix.startswith("gfs.20261006/00/atmos/"):
                entries = "".join(
                    f"<Contents><Key>{name}</Key></Contents>"
                    for name in [
                        name
                        for source in self.runs
                        for name in (source, source + ".idx")
                    ]
                )
            body = (
                "<ListBucketResult><IsTruncated>false</IsTruncated>"
                + entries
                + "</ListBucketResult>"
            ).encode()
        elif key in self.runs and request.method == "HEAD":
            run = self.runs[key]
            headers = {"ETag": run["etag"], "Content-Length": str(run["size"])}
        elif key.endswith(".idx") and key[:-4] in self.runs:
            body = self.runs[key[:-4]]["index_bytes"]
        elif key in self.runs:
            run = self.runs[key]
            byte_range = request.headers["range"]
            assert request.headers["if-match"] == run["etag"]
            body = run["ranges"][byte_range]
            status = 206
            headers = {
                "ETag": '"different-version"'
                if control().get("gfs_mismatch")
                else run["etag"],
                "Content-Range": f"{byte_range.replace('=', ' ')}/{run['size']}",
                "Content-Length": str(len(body)),
            }
        else:
            raise ValueError("Unexpected scientific source request")
        event(
            {
                "method": request.method,
                "key": key,
                "bytes": len(body),
                "range": request.headers.get("range"),
                "etag": headers.get("ETag"),
            }
        )
        return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body))


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = AviationSettingsStore(
        Path("/app/data/settings/aviation-weather.json"), readonly=True
    )
    mailbox = GfsMailbox(Path("/app/data/gfs-mailbox"), settings)
    store = GfsProductStore(
        Path("/app/data/gfs"), mailbox.root, settings, require_demand=True, clock=clock
    )
    with GfsQuota(mailbox.root, clock=clock) as quota:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(SourceFixture())
        ) as client:
            worker = GfsWorker(
                mailbox,
                store,
                GfsTransport(quota, client=client, clock=clock),
                clock=clock,
                decoder_command=["python", "/acceptance/decoder_fixture.py"],
            )
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(signum, worker.stop)
            await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
