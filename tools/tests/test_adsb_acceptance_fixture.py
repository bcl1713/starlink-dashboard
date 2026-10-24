"""Controlled acceptance must never silently query an unintended ADS-B source."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

FIXTURE = Path(__file__).parents[1] / "acceptance/adsb/backend_fixture.py"


@pytest.fixture
def provider_fixture(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "main",
        SimpleNamespace(
            httpx=SimpleNamespace(AsyncClient=httpx.AsyncClient), app=object()
        ),
    )
    monkeypatch.delenv("ADSB_ACCEPTANCE_FAIL", raising=False)
    return runpy.run_path(str(FIXTURE))


@pytest.mark.parametrize(
    "url",
    [
        "https://api.adsb.lol/v2/mil",
        "https://opendata.adsb.fi/v2/mil",
        "https://opendata.adsb.fi/api/v2/unknown",
        "https://opendata.adsb.fi/api/v2/hex/INVALID",
    ],
)
def test_fixture_rejects_unexpected_provider_contract(provider_fixture, url):
    with pytest.raises(RuntimeError):
        provider_fixture["_respond"](httpx.Request("GET", url))


def test_fixture_returns_millisecond_envelope_and_encoded_selection(provider_fixture):
    response = provider_fixture["_respond"](
        httpx.Request("GET", "https://opendata.adsb.fi/api/v2/hex/00AB12%2C000001")
    )
    payload = response.json()
    assert payload["now"] > 1_700_000_000_000
    assert {record["hex"].upper() for record in payload["ac"]} == {"00AB12", "000001"}


def test_fixture_rejects_runtime_base_mismatch(provider_fixture):
    with pytest.raises(RuntimeError):
        provider_fixture["_client"](
            base_url="https://api.adsb.lol",
            headers={"User-Agent": "starlink-dashboard"},
        )
