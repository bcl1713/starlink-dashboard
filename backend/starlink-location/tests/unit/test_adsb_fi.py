import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.services.adsb_fi import AdsbFiProvider, AdsbProviderError, normalize_contact

NOW = 1791028800000.0
RECORD = {"hex": "00ab12", "lat": 40, "lon": -75, "seen_pos": 2.5}


def normalize(record=RECORD, now=NOW, acquired=NOW, military=False):
    return normalize_contact(record, now, acquired, military)


def test_position_age_not_acquisition_time():
    assert normalize().position_observed_at_ms == 1791028797500
    assert normalize(acquired=NOW + 10000).position_observed_at_ms == 1791028797500


def test_last_position_uses_its_own_age():
    contact = normalize(
        {
            "hex": "00ab12",
            "seen_pos": 0,
            "lastPosition": {"lat": 10, "lon": 20, "seen_pos": 40},
        }
    )
    assert contact.latitude == 10
    assert contact.position_observed_at_ms == NOW - 40000


@pytest.mark.parametrize("age", [None, -1, float("nan"), float("inf"), True, "2"])
def test_invalid_position_age_rejected(age):
    assert normalize({**RECORD, "seen_pos": age}) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("lat", 91),
        ("lat", -91),
        ("lon", 181),
        ("lon", float("nan")),
        ("lat", True),
        ("hex", "~AB1234"),
        ("hex", "GG1234"),
    ],
)
def test_invalid_position_identity_rejected(field, value):
    assert normalize({**RECORD, field: value}) is None


@pytest.mark.parametrize("lat,lon", [(-90, -180), (90, 180)])
def test_coordinate_boundaries_are_valid(lat, lon):
    assert normalize({**RECORD, "lat": lat, "lon": lon}) is not None


def test_never_invent_position_from_message_or_receiver():
    assert (
        normalize(
            {
                "hex": "00ab12",
                "seen": 0,
                "rr_lat": 40,
                "rr_lon": -75,
                "gpsOkLat": 40,
                "gpsOkLon": -75,
            }
        )
        is None
    )
    assert normalize(now=None) is None
    assert normalize(now=NOW + 10000) is None


@pytest.mark.parametrize(
    "flags,expected", [(1, True), (0, False), (None, None), (True, None), ("1", None)]
)
def test_optional_fields_and_classification(flags, expected):
    contact = normalize(
        {
            **RECORD,
            "dbFlags": flags,
            "flight": " RCH1 ",
            "r": " N123 ",
            "t": " C17 ",
            "alt_baro": 0,
            "gs": 0,
        }
    )
    assert contact.military is expected
    assert contact.callsign == "RCH1"
    assert contact.registration == "N123"
    assert contact.aircraft_type == "C17"
    assert contact.track_degrees is None
    assert contact.ground_speed_knots == 0
    assert contact.altitude.model_dump() == {
        "value": 0,
        "unit": "ft",
        "source": "barometric",
    }
    assert normalize({**RECORD, "dbFlags": 0}, military=True).military is True


def test_ground_altitude_and_invalid_optional_fields():
    contact = normalize(
        {**RECORD, "alt_baro": "ground", "alt_geom": 125, "track": 360, "gs": -1}
    )
    assert contact.altitude.source == "geometric"
    assert contact.altitude.value == 125
    assert contact.track_degrees is None
    assert contact.ground_speed_knots is None
    assert normalize({**RECORD, "alt_baro": "ground"}).altitude is None


@pytest.mark.parametrize(
    "payload",
    [
        {"now": NOW},
        {"ac": {}, "now": NOW},
        {"ac": [], "now": "now"},
        {"ac": [], "now": True},
        {"ac": [], "now": 10**400},
        {"ac": [], "now": NOW, "msg": "failure"},
    ],
)
async def test_malformed_envelope_fails(payload):
    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as client:
        with pytest.raises(AdsbProviderError):
            await AdsbFiProvider(client, lambda: NOW / 1000).fetch_military()


async def test_invalid_record_is_isolated_and_endpoints_are_exact():
    paths = []

    def transport(request):
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "now": NOW,
                "ac": [RECORD, {"hex": "~AB1234"}, None],
                "msg": "No error",
            },
        )

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        provider = AdsbFiProvider(client, lambda: NOW / 1000)
        result = await provider.fetch_military()
        assert [c.hex for c in result.contacts] == ["00AB12"]
        assert result.contacts[0].military is True
        await provider.fetch_hex("00AB12")
    assert paths == ["/api/v2/mil", "/api/v2/hex/00AB12"]


@pytest.mark.parametrize("field", ["lat", "lon", "seen_pos", "gs", "track", "alt_baro"])
async def test_overflow_in_mixed_records_keeps_valid_positions(field):
    record = {**RECORD, "hex": "000002", field: 10**400}
    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"now": NOW, "ac": [record, RECORD]})
        ),
    ) as client:
        result = await AdsbFiProvider(client, lambda: NOW / 1000).fetch_military()
    if field in {"lat", "lon", "seen_pos"}:
        assert [c.hex for c in result.contacts] == ["00AB12"]
    else:
        assert [c.hex for c in result.contacts] == ["000002", "00AB12"]
        detail = {
            "gs": "ground_speed_knots",
            "track": "track_degrees",
            "alt_baro": "altitude",
        }[field]
        assert getattr(result.contacts[0], detail) is None


@pytest.mark.parametrize(
    "retry,expected", [("45", 45), ("Sat, 03 Oct 2026 12:01:00 GMT", 60), ("bad", None)]
)
async def test_retry_after_seconds_and_http_date(retry, expected):
    from datetime import datetime, timezone

    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc).timestamp()
    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers={"Retry-After": retry})
        ),
    ) as client:
        with pytest.raises(AdsbProviderError) as error:
            await AdsbFiProvider(client, lambda: now).fetch_military()
        assert error.value.retry_after_seconds == expected


async def test_json_and_transport_failure_are_sanitized():
    for transport in [
        lambda _: httpx.Response(200, content="not JSON secret"),
        lambda request: (_ for _ in ()).throw(
            httpx.ConnectError("secret", request=request)
        ),
    ]:
        async with httpx.AsyncClient(
            base_url="https://opendata.adsb.fi/api",
            transport=httpx.MockTransport(transport),
        ) as client:
            with pytest.raises(AdsbProviderError) as error:
                await AdsbFiProvider(client).fetch_military()
            assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "name,hex_code,age,military",
    [
        ("military", "00AB12", 2.5, True),
        ("explicit", "000002", 40, False),
    ],
)
async def test_saved_provider_fixtures(name, hex_code, age, military):
    fixture = Path(__file__).parents[1] / f"fixtures/adsb_fi/{name}.json"
    payload = json.loads(fixture.read_text())
    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as client:
        provider = AdsbFiProvider(client, lambda: NOW / 1000)
        result = (
            await provider.fetch_military()
            if military
            else await provider.fetch_hex(hex_code)
        )
        assert result.contacts[0].hex == hex_code
        assert result.contacts[0].position_observed_at_ms == NOW - age * 1000
        assert result.contacts[0].military is military


@pytest.mark.parametrize(
    "hexes",
    [
        ["000001", "BAD"],
        ["000001", "000002%2C000003"],
        ["000001", "00002"],
        [f"{i:06X}" for i in range(1001)],
    ],
)
async def test_invalid_batch_is_rejected_before_transport(hexes):
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"now": NOW, "ac": []})

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        with pytest.raises(AdsbProviderError):
            await AdsbFiProvider(client, lambda: NOW / 1000).fetch_hexes(hexes)
    assert requests == []


async def test_empty_batch_skips_transport():
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"now": NOW, "ac": []})

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        result = await AdsbFiProvider(client, lambda: NOW / 1000).fetch_hexes([])
    assert result.contacts == []
    assert requests == []


class PacingClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay
        await asyncio.sleep(0)


async def test_concurrent_endpoints_share_serial_request_start_spacing():
    clock = PacingClock()
    starts = []
    active = 0
    peak = 0

    async def transport(request):
        nonlocal active, peak
        starts.append(clock())
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return httpx.Response(200, json={"now": NOW, "ac": []})

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        provider = AdsbFiProvider(
            client, lambda: NOW / 1000, monotonic_source=clock, sleep=clock.sleep
        )
        await asyncio.gather(
            provider.fetch_military(),
            provider.fetch_hexes(["00AB12", "000002"]),
            provider.fetch_hex("ABCDEF"),
        )
    assert starts == pytest.approx([100, 101.1, 102.2])
    assert peak == 1


@pytest.mark.parametrize("retry", ["60", "Sat, 03 Oct 2026 12:01:00 GMT"])
async def test_retry_after_is_shared_across_endpoints_without_long_sleep(retry):
    clock = PacingClock()
    paths = []

    def transport(request):
        paths.append(request.url.path)
        return (
            httpx.Response(429, headers={"Retry-After": retry})
            if len(paths) == 1
            else httpx.Response(200, json={"now": NOW, "ac": []})
        )

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        provider = AdsbFiProvider(
            client, lambda: NOW / 1000, monotonic_source=clock, sleep=clock.sleep
        )
        with pytest.raises(AdsbProviderError):
            await provider.fetch_military()
        clock.now += 10
        with pytest.raises(AdsbProviderError) as error:
            await provider.fetch_hex("00AB12")
        assert error.value.retry_after_seconds == pytest.approx(50)
        assert len(paths) == 1
        assert clock.sleeps == []
        clock.now += 50
        await provider.fetch_hex("00AB12")
        assert len(paths) == 2


@pytest.mark.parametrize("failure", ["cancel", "transport"])
async def test_consumed_slot_survives_cancellation_or_transport_failure(failure):
    clock = PacingClock()
    started = asyncio.Event()
    starts = []

    async def transport(request):
        starts.append(clock())
        if len(starts) == 1:
            started.set()
            if failure == "cancel":
                await asyncio.Event().wait()
            raise httpx.ConnectError("failure", request=request)
        return httpx.Response(200, json={"now": NOW, "ac": []})

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        provider = AdsbFiProvider(
            client, lambda: NOW / 1000, monotonic_source=clock, sleep=clock.sleep
        )
        task = asyncio.create_task(provider.fetch_military())
        try:
            await asyncio.wait_for(started.wait(), 1)
            if failure == "cancel":
                task.cancel()
            with pytest.raises(
                asyncio.CancelledError if failure == "cancel" else AdsbProviderError
            ):
                await task
            await provider.fetch_hex("00AB12")
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert starts == pytest.approx([100, 101.1])


async def test_invalid_or_empty_input_does_not_consume_request_slot():
    clock = PacingClock()
    starts = []

    def transport(request):
        starts.append(clock())
        return httpx.Response(200, json={"now": NOW, "ac": []})

    async with httpx.AsyncClient(
        base_url="https://opendata.adsb.fi/api",
        transport=httpx.MockTransport(transport),
    ) as client:
        provider = AdsbFiProvider(
            client, lambda: NOW / 1000, monotonic_source=clock, sleep=clock.sleep
        )
        await provider.fetch_hexes([])
        with pytest.raises(AdsbProviderError):
            await provider.fetch_hexes(["invalid"])
        await provider.fetch_military()
    assert starts == [100]
    assert clock.sleeps == []
