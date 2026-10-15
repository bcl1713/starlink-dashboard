"""Source-shaped HTTP controls exercise the real bounded range downloader."""

import hashlib

import httpx
import pytest

from app.models.aviation_grid import RangeRef, SourceRef


@pytest.mark.parametrize(
    "status,headers,body",
    [
        (200, {"ETag": '"v1"'}, b"abcd"),
        (206, {"ETag": '"v2"', "Content-Range": "bytes 8-11/16"}, b"abcd"),
        (206, {"ETag": '"v1"', "Content-Range": "bytes 7-10/16"}, b"abcd"),
        (206, {"ETag": '"v1"', "Content-Range": "bytes 8-11/16"}, b"ab"),
    ],
)
async def test_invalid_range_never_leaves_a_published_file(
    tmp_path, status, headers, body
):
    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    def exchange(request):
        assert request.headers["if-match"] == '"v1"'
        assert request.headers["range"] == "bytes=8-11"
        return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body))

    async with httpx.AsyncClient(transport=httpx.MockTransport(exchange)) as client:
        with GfsQuota(tmp_path / "quota") as quota:
            transport = GfsTransport(quota, client=client)
            with pytest.raises(ValueError):
                await transport.download(
                    RangeRef(SourceRef("gfs.file", '"v1"', 16), 8, 11, "u", 50000),
                    tmp_path / "u.grib2",
                )
    assert not (tmp_path / "u.grib2").exists()
    assert not list(tmp_path.glob("*.partial"))


async def test_range_hash_is_over_exact_received_bytes(tmp_path):
    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                206,
                headers={"ETag": '"v1"', "Content-Range": "bytes 8-11/16"},
                stream=httpx.ByteStream(b"abcd"),
            )
        )
    ) as client:
        with GfsQuota(tmp_path / "quota") as quota:
            transport = GfsTransport(quota, client=client)
            digest = await transport.download(
                RangeRef(SourceRef("gfs.file", '"v1"', 16), 8, 11, "u", 50000),
                tmp_path / "u.grib2",
            )
    assert digest == hashlib.sha256(b"abcd").hexdigest()
    assert (tmp_path / "u.grib2").read_bytes() == b"abcd"


@pytest.mark.parametrize("replace_source", [False, True])
async def test_acquisition_requires_actual_key_and_final_unchanged_validator(
    tmp_path, replace_source
):
    from datetime import datetime, timezone

    from app.models.aviation_grid import GfsSelection
    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    run = int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp())
    key = "gfs.20261006/00/atmos/gfs.t00z.pgrb2.0p25.f000"
    index = b"1:0:d=2026100600:TMP:500 mb:anl:\n2:8:d=2026100600:UGRD:500 mb:anl:\n3:16:d=2026100600:VGRD:500 mb:anl:\n4:24:d=2026100600:PRES:surface:anl:\n"
    heads = []

    def exchange(request):
        if request.method == "HEAD":
            heads.append(request)
            return httpx.Response(
                200,
                headers={
                    "etag": '"v2"' if replace_source and len(heads) == 3 else '"v1"',
                    "content-length": "32",
                },
                stream=httpx.ByteStream(b""),
            )
        if request.url.path == "/":
            prefix = request.url.params["prefix"]
            item = ""
            if prefix == "gfs.20261006/":
                item = (
                    "<CommonPrefixes><Prefix>gfs.20261006/00/</Prefix></CommonPrefixes>"
                )
            elif prefix.startswith("gfs.20261006/00/atmos/"):
                item = f"<Contents><Key>{key}</Key></Contents><Contents><Key>{key}.idx</Key></Contents>"
            body = f"<ListBucketResult>{item}<IsTruncated>false</IsTruncated></ListBucketResult>".encode()
            return httpx.Response(200, stream=httpx.ByteStream(body))
        if request.url.path.endswith(".idx"):
            return httpx.Response(200, stream=httpx.ByteStream(index))
        bounds = request.headers["range"].removeprefix("bytes=")
        return httpx.Response(
            206,
            headers={"etag": '"v1"', "content-range": f"bytes {bounds}/32"},
            stream=httpx.ByteStream(b"abcdefgh"),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(exchange)) as client:
        with GfsQuota(tmp_path / "quota", clock=lambda: run) as quota:
            transport = GfsTransport(quota, client=client, clock=lambda: run)
            if replace_source:
                with pytest.raises(ValueError):
                    await transport.acquire(GfsSelection(), tmp_path / "stage")
                assert not (tmp_path / "stage").exists()
            else:
                bundle = await transport.acquire(GfsSelection(), tmp_path / "stage")
                assert bundle.run_at_ms == run * 1000
                assert bundle.lead_seconds == 0
                assert len(bundle.paths) == 4
                assert all(path.read_bytes() == b"abcdefgh" for path in bundle.paths)
    assert len(heads) == 3


async def test_cancelled_stream_releases_its_slot_and_partial_without_cancelling_peer(
    tmp_path,
):
    import asyncio

    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    entered, finish, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await finish.wait()
            yield b"abcd"

        async def aclose(self):
            closed.set()

    def exchange(request):
        stream = (
            SlowStream() if request.url.path == "/slow" else httpx.ByteStream(b"abcd")
        )
        return httpx.Response(
            206,
            headers={"etag": '"v1"', "content-range": "bytes 8-11/16"},
            stream=stream,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(exchange)) as client:
        with GfsQuota(tmp_path / "quota") as quota:
            transport = GfsTransport(quota, client=client)
            pending = asyncio.create_task(
                transport.download(
                    RangeRef(SourceRef("slow", '"v1"', 16), 8, 11, "u", 50000),
                    tmp_path / "slow.grib2",
                )
            )
            try:
                await asyncio.wait_for(entered.wait(), 1)
                await transport.download(
                    RangeRef(SourceRef("peer", '"v1"', 16), 8, 11, "v", 50000),
                    tmp_path / "peer.grib2",
                )
            finally:
                pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await pending
            assert closed.is_set()
            assert not list(tmp_path.glob("*.partial"))
            assert not (tmp_path / "slow.grib2").exists()
            assert (tmp_path / "peer.grib2").read_bytes() == b"abcd"
            one, two = quota.reserve(1), quota.reserve(1)
            quota.release(one)
            quota.release(two)


async def test_absolute_deadline_closes_stalled_body_and_releases_budget(
    tmp_path, monkeypatch
):
    import asyncio

    from app.services.aviation_weather.gfs import transport as module
    from app.services.aviation_weather.gfs.quota import GfsQuota

    closed = asyncio.Event()

    class Stalled(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b"abcd"

        async def aclose(self):
            closed.set()

    monkeypatch.setattr(module, "EXCHANGE_SECONDS", 0.01)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(206, stream=Stalled())
        )
    ) as client:
        with GfsQuota(tmp_path / "quota") as quota:
            transport = module.GfsTransport(quota, client=client)
            with pytest.raises(TimeoutError):
                await transport.download(
                    RangeRef(SourceRef("stalled", '"v1"', 16), 8, 11, "u", 50000),
                    tmp_path / "u.grib2",
                )
            assert closed.is_set()
            assert not list(tmp_path.glob("*.partial"))
            assert not (tmp_path / "u.grib2").exists()
            first, second = quota.reserve(1), quota.reserve(1)
            quota.release(first)
            quota.release(second)


async def test_truncated_listing_is_not_a_complete_inventory(tmp_path):
    from app.services.aviation_weather.gfs.quota import GfsQuota
    from app.services.aviation_weather.gfs.transport import GfsTransport

    body = b"<ListBucketResult><IsTruncated>true</IsTruncated></ListBucketResult>"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=httpx.ByteStream(body))
        )
    ) as client:
        with GfsQuota(tmp_path / "quota") as quota:
            transport = GfsTransport(quota, client=client)
            with pytest.raises(ValueError):
                await transport._list("gfs.20261006/", "/")
