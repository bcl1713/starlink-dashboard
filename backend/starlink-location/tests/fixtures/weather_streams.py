"""Controlled socket I/O; production HTTP, host, address and TLS policy stay real."""

import asyncio
import ssl


class WeatherWriter:
    def __init__(self):
        self.written = bytearray()
        self.close_calls = 0
        self.wait_closed_calls = 0

    def write(self, body):
        self.written.extend(body)

    async def drain(self):
        pass

    def close(self):
        self.close_calls += 1

    async def wait_closed(self):
        self.wait_closed_calls += 1


def http_response(body=b"{}", content_type="application/json", status=200):
    return (
        f"HTTP/1.1 {status} OK\r\nContent-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body


class WeatherStreams:
    def __init__(self, wire=None, addresses=None):
        self.wire = wire
        self.addresses = addresses or ["1.1.1.1"]
        self.readers = []
        self.writers = []
        self.dials = []
        self.opened = asyncio.Event()

    async def resolve(self, host, timeout):
        return self.addresses

    async def open(self, ip, host, context, timeout):
        assert context.check_hostname
        assert context.verify_mode == ssl.CERT_REQUIRED
        self.dials.append((ip, host))
        reader = asyncio.StreamReader()
        writer = WeatherWriter()
        self.readers.append(reader)
        self.writers.append(writer)
        if self.wire is not None:
            reader.feed_data(self.wire)
            reader.feed_eof()
        self.opened.set()
        return reader, writer
