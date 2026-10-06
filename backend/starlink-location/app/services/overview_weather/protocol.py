"""Bounded HTTP/1.1 exchange; the caller alone owns writer cleanup."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import h11

from .clock import WeatherClock


class WeatherUnavailable(Exception):
    def __init__(self, retry_after_seconds: int = 30):
        super().__init__("Weather unavailable")
        self.retry_after_seconds = min(300, max(30, retry_after_seconds))


@dataclass(frozen=True)
class WeatherPayload:
    body: bytes
    headers: Mapping[str, str]


def remaining(deadline: float, clock: WeatherClock) -> float:
    duration = deadline - clock.monotonic()
    if duration <= 0:
        raise TimeoutError("Weather deadline elapsed")
    return duration


def retry_after(value: str, clock: WeatherClock) -> int:
    try:
        delay = (
            int(value)
            if value.isdecimal()
            else int(parsedate_to_datetime(value).timestamp() - clock.utc_ms() / 1000)
        )
        return min(300, max(30, delay))
    except (ValueError, TypeError, OverflowError):
        return 30


async def exchange_http(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    path: str,
    max_bytes: int,
    expected_type: str,
    deadline: float,
    clock: WeatherClock,
) -> WeatherPayload:
    connection = h11.Connection(h11.CLIENT, max_incomplete_event_size=32768)
    request = h11.Request(
        method="GET",
        target=path,
        headers=[
            ("Host", host),
            ("Connection", "close"),
            ("Accept", expected_type),
            ("Accept-Encoding", "identity"),
        ],
    )
    writer.write(connection.send(request))
    writer.write(connection.send(h11.EndOfMessage()))
    async with asyncio.timeout(remaining(deadline, clock)):
        await writer.drain()
    header_buffer = bytearray()
    headers: dict[str, str] | None = None
    body = bytearray()
    eof = False
    try:
        while True:
            event = connection.next_event()
            if event is h11.NEED_DATA:
                if eof:
                    raise WeatherUnavailable()
                async with asyncio.timeout(remaining(deadline, clock)):
                    chunk = await reader.read(16384)
                eof = not chunk
                if headers is None:
                    header_buffer.extend(chunk)
                    boundary = header_buffer.find(b"\r\n\r\n")
                    header_size = boundary + 4 if boundary >= 0 else len(header_buffer)
                    if header_size > 32768:
                        raise WeatherUnavailable()
                    if boundary >= 0:
                        raw = header_buffer[:boundary].lower().split(b"\r\n")[1:]
                        names = [line.split(b":", 1)[0] for line in raw]
                        if names.count(b"content-length") > 1 or (
                            b"content-length" in names and b"transfer-encoding" in names
                        ):
                            raise WeatherUnavailable()
                connection.receive_data(chunk)
            elif isinstance(event, h11.Response):
                headers = {
                    key.decode("ascii").lower(): value.decode("ascii")
                    for key, value in event.headers
                }
                if event.status_code != 200:
                    raise WeatherUnavailable(
                        retry_after(headers.get("retry-after", "30"), clock)
                    )
                if (
                    headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != expected_type
                    or headers.get("content-encoding", "identity").lower() != "identity"
                    or int(headers.get("content-length", "0")) > max_bytes
                ):
                    raise WeatherUnavailable()
                header_buffer.clear()
            elif isinstance(event, h11.Data):
                body.extend(event.data)
                if len(body) > max_bytes:
                    raise WeatherUnavailable()
            elif isinstance(event, h11.EndOfMessage):
                if headers is None or connection.trailing_data[0]:
                    raise WeatherUnavailable()
                return WeatherPayload(bytes(body), headers)
            else:
                raise WeatherUnavailable()
    except (h11.ProtocolError, UnicodeError, ValueError) as error:
        raise WeatherUnavailable() from error
