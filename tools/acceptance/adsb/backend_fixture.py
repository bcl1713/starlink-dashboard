"""Test-only launcher: real app/lifespan with ADS-B-only controlled transport.

Mount this file read-only in the candidate image. No production test endpoint.
ADSB_ACCEPTANCE_FAIL=1 makes subsequent provider acquisition fail after restart.
"""

import json
import os
import time
from pathlib import Path

import httpx
import main

_original_client = httpx.AsyncClient


def _respond(request: httpx.Request) -> httpx.Response:
    if request.url.host != "api.adsb.lol":
        raise RuntimeError("Acceptance transport must be ADS-B-only")
    if os.getenv("ADSB_ACCEPTANCE_FAIL") == "1":
        return httpx.Response(503)
    records = json.loads(Path(__file__).with_name("provider.json").read_text())["ac"]
    selected = (
        records[:1]
        if request.url.path == "/v2/mil"
        else [
            record
            for record in records
            if record["hex"].upper()
            in request.url.path.rsplit("/", 1)[-1].upper().split(",")
        ]
    )
    return httpx.Response(200, json={"now": time.time() * 1000, "ac": selected})


def _client(*args, **kwargs):
    if str(kwargs.get("base_url", "")).rstrip("/") == "https://api.adsb.lol":
        kwargs["transport"] = httpx.MockTransport(_respond)
    return _original_client(*args, **kwargs)


main.httpx.AsyncClient = _client
app = main.app
