import asyncio
import ssl

import pytest

from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.transport import PinnedWeatherTransport
from tests.fixtures.weather_streams import WeatherStreams, http_response

URL = "https://api.rainviewer.com/public/weather-maps.json"


async def fetch(streams, url=URL, seconds=5, attempts=None):
    clock = WeatherClock()
    transport = PinnedWeatherTransport(clock, streams.resolve, streams.open)
    return await transport.fetch(
        url,
        131072,
        "application/json",
        clock.monotonic() + seconds,
        before_attempt=lambda: attempts.append(1) if attempts is not None else None,
    )


async def test_numeric_dial_original_host_and_exact_once_completion():
    streams = WeatherStreams(http_response())
    assert (await fetch(streams)).body == b"{}"
    assert streams.dials == [("1.1.1.1", "api.rainviewer.com")]
    assert b"Host: api.rainviewer.com" in streams.writers[0].written
    assert streams.writers[0].close_calls == 1
    assert streams.writers[0].wait_closed_calls == 1


async def test_opaque_radar_tile_path_uses_pinned_verified_provider_connection():
    streams = WeatherStreams(http_response(b"png", "image/png"))
    clock = WeatherClock()
    transport = PinnedWeatherTransport(clock, streams.resolve, streams.open)
    payload = await transport.fetch(
        "https://tilecache.rainviewer.com/v2/radar/f1fa64870793/512/2/1/1/2/1_1.png",
        2097152,
        "image/png",
        clock.monotonic() + 5,
        before_attempt=lambda: None,
    )
    assert payload.body == b"png"
    assert streams.dials == [("1.1.1.1", "tilecache.rainviewer.com")]
    assert (
        b"GET /v2/radar/f1fa64870793/512/2/1/1/2/1_1.png HTTP/1.1"
        in streams.writers[0].written
    )
    assert streams.writers[0].close_calls == 1
    assert streams.writers[0].wait_closed_calls == 1


async def test_cancel_after_open_closes_once():
    streams = WeatherStreams()
    task = asyncio.create_task(fetch(streams))
    await streams.opened.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert streams.writers[0].close_calls == 1
    assert streams.writers[0].wait_closed_calls == 1


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "ff02::1", "::ffff:127.0.0.1"],
)
async def test_rejects_nonpublic_addresses_without_dial(ip):
    streams = WeatherStreams(http_response(), [ip])
    with pytest.raises(WeatherUnavailable):
        await fetch(streams)
    assert streams.dials == []


@pytest.mark.parametrize(
    "url",
    [
        "http://api.rainviewer.com/public/weather-maps.json",
        URL + "?url=http://localhost",
        URL + "#fragment",
        "https://api.rainviewer.com.evil/public/weather-maps.json",
        "https://api.rainviewer.com:443/public/weather-maps.json",
        "https://tilecache.rainviewer.com/v2/radar/1/../private",
    ],
)
async def test_rejects_unconstructed_urls(url):
    streams = WeatherStreams(http_response())
    with pytest.raises(WeatherUnavailable):
        await fetch(streams, url)
    assert streams.dials == []


async def test_deadline_covers_dns_and_body_without_reset(monkeypatch):
    real_timeout = asyncio.timeout
    budgets = []
    scopes = []

    def record_timeout(seconds):
        budgets.append(seconds)
        scope = real_timeout(seconds)
        scopes.append(scope)
        return scope

    monkeypatch.setattr(asyncio, "timeout", record_timeout)

    # Keep the three paths in this existing case: collection counts stay stable.
    async def check_phase(phase):
        now = [0.0]
        clock = WeatherClock(monotonic=lambda: now[0])
        deadline = 0.025
        streams = WeatherStreams()
        attempts = []
        budgets.clear()
        scopes.clear()

        async def resolve(host, timeout):
            assert timeout == pytest.approx(0.025)
            if phase == "dns":
                await asyncio.Event().wait()
            now[0] = 0.025 if phase == "before_open" else 0.015
            return ["1.1.1.1"]

        async def open_stream(ip, host, context, timeout):
            assert timeout == pytest.approx(0.010)
            reader, writer = await streams.open(ip, host, context, timeout)
            # Supply complete headers, then stall the body without feeding EOF.
            reader.feed_data(http_response()[:-2])
            return reader, writer

        transport = PinnedWeatherTransport(clock, resolve, open_stream)
        with pytest.raises(WeatherUnavailable) as caught:
            await transport.fetch(
                URL,
                131072,
                "application/json",
                deadline,
                before_attempt=lambda: attempts.append(1),
            )
        assert isinstance(caught.value.__cause__, TimeoutError)
        if phase == "body":
            # DNS, connect, drain, headers, body all share the original deadline.
            assert budgets == pytest.approx([0.025, 0.010, 0.010, 0.010, 0.010])
            assert now[0] == 0.015
            assert attempts == [1]
            assert streams.dials == [("1.1.1.1", "api.rainviewer.com")]
            assert len(streams.writers) == 1
            assert streams.writers[0].close_calls == 1
            assert streams.writers[0].wait_closed_calls == 1
        else:
            assert budgets == pytest.approx([0.025])
            assert attempts == []
            assert streams.dials == []
            assert streams.writers == []
        if phase == "before_open":
            assert not any(scope.expired() for scope in scopes)
        else:
            assert scopes[-1].expired()
            assert isinstance(caught.value.__cause__.__cause__, asyncio.CancelledError)

    for phase in ("body", "before_open", "dns"):
        await check_phase(phase)


async def test_tls_failure_counts_attempt_and_never_disables_verification():
    streams = WeatherStreams(addresses=["1.1.1.1", "8.8.8.8"])

    async def untrusted(ip, host, context, timeout):
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        raise ssl.SSLCertVerificationError("certificate mismatch")

    streams.open = untrusted
    attempts = []
    with pytest.raises(WeatherUnavailable):
        await fetch(streams, attempts=attempts)
    assert len(attempts) == 2
