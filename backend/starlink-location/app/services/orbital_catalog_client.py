"""One bounded, non-retrying provider operation; no redirects."""

import asyncio
import json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

PROVIDER_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=JSON"
MAX_BYTES = 16 * 1024 * 1024


class ProviderFailure(Exception):
    def __init__(self, message: str, suspended=False, retry_after=None):
        super().__init__(message)
        self.suspended = suspended
        self.retry_after = retry_after


def retry_after(value: str | None, now: datetime) -> datetime | None:
    if not value:
        return None
    try:
        if value.isdecimal():
            return now + timedelta(seconds=int(value))
        instant = parsedate_to_datetime(value)
        return instant if instant.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


async def fetch_catalog(client: httpx.AsyncClient, now: datetime) -> object:
    async def download():
        async with client.stream(
            "GET", PROVIDER_URL, timeout=20, follow_redirects=False
        ) as response:
            if response.status_code != 200:
                raise ProviderFailure(
                    f"Provider HTTP {response.status_code}; operator resume required",
                    True,
                    retry_after(response.headers.get("retry-after"), now),
                )
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_BYTES:
                    raise ProviderFailure("Provider response exceeded 16 MiB")
                body.extend(chunk)
            try:
                return json.loads(body)
            except (ValueError, UnicodeError) as error:
                raise ProviderFailure("Malformed provider JSON") from error

    return await asyncio.wait_for(download(), timeout=20)
