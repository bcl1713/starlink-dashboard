"""HTTP CPU profiles are diagnostic-only and opt in per request."""

import pstats

import httpx
import pytest
from fastapi import FastAPI

from tools.acceptance.overview_history.http_profile import HTTPProfile


@pytest.mark.asyncio
async def test_http_cpu_profile_is_explicit_and_covers_serialization(tmp_path):
    app = FastAPI()

    @app.get("/api/overview-history")
    async def history():
        return {"series": {"latency": [[n, n / 2] for n in range(100)]}}

    output = tmp_path / "http-response.prof"
    app.add_middleware(HTTPProfile, output=output)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        plain = await client.get("/api/overview-history")
        assert not output.exists()
        profiled = await client.get(
            "/api/overview-history", headers={"X-Overview-CPU-Profile": "1"}
        )
    assert profiled.json() == plain.json()
    keys = pstats.Stats(str(output)).stats
    assert any("jsonable_encoder" in key[2] for key in keys)
    assert any("encode" in key[2] for key in keys)
