"""Real-client profiling controls retain cache semantics and truthful counters."""

import asyncio
import json

import httpx
import pytest
from acceptance.overview_history.seed import write_seed
from acceptance.overview_history.trace import QueryTrace
from profile_overview_history import OverviewHistoryReader, measure

METRICS = (
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_altitude_feet",
    "starlink_dish_speed_knots",
    "starlink_dish_heading_degrees",
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
    "starlink_signal_quality_percent",
)


def handler(request):
    query = request.url.params
    start, end, step = (int(query[key]) for key in ("start", "end", "step"))
    metrics = (
        METRICS
        if query["query"].startswith("{")
        else [name for name in METRICS if name in query["query"]]
    )
    return httpx.Response(
        200,
        json={
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {
                            "__name__": name,
                            "job": "starlink-location",
                            "instance": "starlink-location:8000",
                        },
                        "values": [[t, "0"] for t in range(start, end + 1, step)],
                    }
                    for name in metrics
                ],
            },
        },
    )


@pytest.mark.parametrize("window,step", [(3600, 2), (3601, 3)])
def test_unchanged_grid_reuses_completed_snapshot(window, step):
    result = asyncio.run(
        measure(
            window=window,
            cadence=1,
            mode="incremental",
            samples=1,
            end=1800000000,
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["step_seconds"] == step
    assert result["warm_queries"] == 0
    assert result["second_reader_queries_max"] == 0
    assert result["query_span_max_seconds"] is None


def test_tail_and_completed_reuse_are_measured_separately():
    result = asyncio.run(
        measure(
            window=1800,
            cadence=1,
            mode="incremental",
            samples=2,
            end=1800000000,
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["cold_queries"] == 16
    assert result["warm_queries"] == 32
    assert result["warm_evaluation_points"] == 624
    assert result["query_span_max_seconds"] == 11
    assert result["second_reader_queries_max"] == 0
    assert result["max_upstream_concurrency"] <= 3
    assert result["upstream_active_at_end"] == 0
    assert result["returned_points"] <= 46826


def test_full_control_repeats_work_after_completed_reads():
    result = asyncio.run(
        measure(
            window=300,
            cadence=5,
            mode="full",
            samples=1,
            end=1800000000,
            transport=httpx.MockTransport(handler),
        )
    )
    assert result["warm_queries"] == 32
    assert result["query_span_max_seconds"] == 300
    assert result["second_reader_queries_max"] == 16


def test_transport_failure_is_reported_and_drains_shared_work():
    def fail(request):
        raise httpx.ConnectError("controlled failure", request=request)

    result = asyncio.run(
        measure(
            window=300,
            cadence=1,
            mode="incremental",
            samples=1,
            end=1800000000,
            transport=httpx.MockTransport(fail),
        )
    )
    assert result["status"] == "failed"
    assert result["errors"]
    assert result["upstream_active_at_end"] == 0


def test_seed_has_one_source_and_reproducible_relative_observations(tmp_path):
    first, second = tmp_path / "one.openmetrics", tmp_path / "two.openmetrics"
    write_seed(first, 1800000000)
    write_seed(second, 1800001000)
    rows = [line for line in first.read_text().splitlines() if not line.startswith("#")]
    shifted = [
        line for line in second.read_text().splitlines() if not line.startswith("#")
    ]
    assert len(rows) == 11 * 4201
    for name in METRICS:
        points = [line for line in rows if line.startswith(name + "{")]
        assert len(points) == 4201
        assert all(
            'instance="starlink-location:8000",job="starlink-location"' in line
            for line in points
        )
        assert [float(line.rsplit(" ", 1)[1]) for line in points] == sorted(
            float(line.rsplit(" ", 1)[1]) for line in points
        )
    assert [line.rsplit(" ", 1)[0] for line in rows] == [
        line.rsplit(" ", 1)[0] for line in shifted
    ]
    assert any("} 0 " in line for line in rows)
    assert first.read_text().endswith("# EOF\n")


def test_seed_and_profiler_reject_invalid_inputs(tmp_path):
    with pytest.raises(ValueError):
        write_seed(tmp_path / "bad", 1800000000, -1)
    with pytest.raises(ValueError):
        asyncio.run(
            measure(
                window=300,
                cadence=1,
                mode="incremental",
                samples=0,
                end=1800000000,
                transport=httpx.MockTransport(handler),
            )
        )


def test_report_is_json_serializable():
    result = asyncio.run(
        measure(
            window=300,
            cadence=1,
            mode="incremental",
            samples=1,
            end=1800000000,
            transport=httpx.MockTransport(handler),
        )
    )
    json.dumps(result, allow_nan=False)


def test_cancelled_http_waiter_does_not_cancel_shared_refresh():
    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(request):
            entered.set()
            await release.wait()
            return handler(request)

        trace = QueryTrace(httpx.MockTransport(delayed))
        async with httpx.AsyncClient(
            base_url="http://prometheus", transport=trace
        ) as client:
            reader = OverviewHistoryReader(
                client, get_window_seconds=lambda: 300, time_source=lambda: 1800000000
            )
            first = asyncio.create_task(reader.read())
            await entered.wait()
            second = asyncio.create_task(reader.read())
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            release.set()
            bundle = await second
            assert bundle["window_seconds"] == 300
            assert trace.queries == 16
            assert trace.active == 0
            await reader.aclose()

    asyncio.run(exercise())


def test_upstream_http_failures_are_counted():
    async def exercise():
        trace = QueryTrace(httpx.MockTransport(lambda _: httpx.Response(503)))
        async with httpx.AsyncClient(
            base_url="http://prometheus", transport=trace
        ) as client:
            await client.get(
                "/api/v1/query_range",
                params={"start": 1, "end": 2, "step": 1, "query": "metric"},
            )
        assert trace.errors == 1
        assert trace.active == 0

    asyncio.run(exercise())
