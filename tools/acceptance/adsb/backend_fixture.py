"""Test-only launcher: real app/lifespan with ADS-B-only controlled transport.

Mount this file read-only in the candidate image. No production test endpoint.
ADSB_ACCEPTANCE_FAIL=1 makes subsequent provider acquisition fail after restart.
"""

import json
import os
import re
import time
from pathlib import Path

import httpx
import main

_original_client = httpx.AsyncClient


def _respond(request: httpx.Request) -> httpx.Response:
    if (
        request.method != "GET"
        or request.url.scheme != "https"
        or request.url.host != "opendata.adsb.fi"
        or request.url.port not in (None, 443)
        or request.url.query
        or re.fullmatch(
            r"/api/v2/(mil|hex/[0-9A-F]{6}(?:,[0-9A-F]{6})*)", request.url.path
        )
        is None
    ):
        raise RuntimeError(
            "Acceptance transport must match the anonymous adsb.fi contract"
        )
    if os.getenv("ADSB_ACCEPTANCE_FAIL") == "1":
        return httpx.Response(503)
    records = json.loads(Path(__file__).with_name("provider.json").read_text())["ac"]
    selected = (
        records[:1]
        if request.url.path == "/api/v2/mil"
        else [
            record
            for record in records
            if record["hex"].upper()
            in request.url.path.rsplit("/", 1)[-1].upper().split(",")
        ]
    )
    return httpx.Response(200, json={"now": time.time() * 1000, "ac": selected})


def _client(*args, **kwargs):
    base = str(kwargs.get("base_url", "")).rstrip("/")
    agent = httpx.Headers(kwargs.get("headers", {})).get("User-Agent", "")
    if (
        base == "https://opendata.adsb.fi/api"
        or agent
        == "starlink-dashboard (+https://github.com/bcl1713/starlink-dashboard/issues)"
    ):
        if base != "https://opendata.adsb.fi/api":
            raise RuntimeError("Unexpected ADS-B runtime base URL")
        kwargs["transport"] = httpx.MockTransport(_respond)
    return _original_client(*args, **kwargs)


main.httpx.AsyncClient = _client
app = main.app
