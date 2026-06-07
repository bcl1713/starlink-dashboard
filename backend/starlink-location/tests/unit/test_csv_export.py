"""Unit tests for Starlink telemetry CSV export."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from app.api.export import csv_export, prometheus


GROUND_ENTRY_COLUMNS = [
    "ground_entry_latitude",
    "ground_entry_longitude",
    "ground_entry_city",
    "ground_entry_country",
    "ground_entry_ip",
]


def _sample_export_row() -> dict[str, float | str]:
    return {
        "latitude": 40.0,
        "longitude": -73.0,
        "altitude_feet": 10000.0,
        "speed_knots": 250.0,
        "heading_degrees": 180.0,
        "latency_ms": 45.0,
        "throughput_down_mbps": 120.0,
        "throughput_up_mbps": 25.0,
        "packet_loss_percent": 0.5,
        "obstruction_percent": 5.0,
        "signal_quality_percent": 98.0,
        "ground_entry_latitude": 41.2565,
        "ground_entry_longitude": -95.9345,
        "ground_entry_city": "Omaha",
        "ground_entry_country": "US",
        "ground_entry_ip": "203.0.113.10",
    }


def test_csv_columns_include_ground_entry_fields() -> None:
    assert csv_export.CSV_COLUMNS[0] == "timestamp"
    for column in GROUND_ENTRY_COLUMNS:
        assert column in csv_export.CSV_COLUMNS

    metric_names = {metric.metric for metric in prometheus.EXPORT_METRICS}
    assert "starlink_ground_entry_point_latitude_degrees" in metric_names
    assert "starlink_ground_entry_point_longitude_degrees" in metric_names
    assert "starlink_ground_entry_point_location" in metric_names


@pytest.mark.anyio("asyncio")
async def test_query_all_metrics_includes_ground_entry_numeric_and_label_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(minutes=5)
    timestamp = 1710000000.0

    async def fake_query_metric_range(
        metric: str,
        start: datetime,
        end: datetime,
        step: int,
    ) -> list[dict[str, object]]:
        if metric == "starlink_dish_latitude_degrees":
            return [{"metric": {}, "values": [[timestamp, "40.0"]]}]
        if metric == "starlink_ground_entry_point_latitude_degrees":
            return [{"metric": {}, "values": [[timestamp, "41.2565"]]}]
        if metric == "starlink_ground_entry_point_longitude_degrees":
            return [{"metric": {}, "values": [[timestamp, "-95.9345"]]}]
        if metric == "starlink_ground_entry_point_location":
            return [
                {
                    "metric": {
                        "city": "Omaha",
                        "country": "US",
                        "ip": "203.0.113.10",
                    },
                    "values": [[timestamp, "1"]],
                }
            ]
        return []

    monkeypatch.setattr(prometheus, "query_metric_range", fake_query_metric_range)

    data = await prometheus.query_all_metrics(start, end, step=10)

    assert data[timestamp]["latitude"] == 40.0
    assert data[timestamp]["ground_entry_latitude"] == 41.2565
    assert data[timestamp]["ground_entry_longitude"] == -95.9345
    assert data[timestamp]["ground_entry_city"] == "Omaha"
    assert data[timestamp]["ground_entry_country"] == "US"
    assert data[timestamp]["ground_entry_ip"] == "203.0.113.10"


def test_generate_csv_includes_ground_entry_columns_and_values() -> None:
    content = csv_export.generate_csv({1710000000.0: _sample_export_row()})
    rows = list(csv.reader(io.StringIO(content)))

    assert rows[0] == csv_export.CSV_COLUMNS

    header = rows[0]
    values = rows[1]
    assert values[header.index("ground_entry_latitude")] == "41.2565"
    assert values[header.index("ground_entry_longitude")] == "-95.9345"
    assert values[header.index("ground_entry_city")] == "Omaha"
    assert values[header.index("ground_entry_country")] == "US"
    assert values[header.index("ground_entry_ip")] == "203.0.113.10"


def test_export_starlink_csv_response_includes_ground_entry_columns(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(minutes=5)

    async def fake_query_all_metrics(
        start: datetime,
        end: datetime,
        step: int,
    ) -> dict[float, dict[str, float | str]]:
        return {1710000000.0: _sample_export_row()}

    monkeypatch.setattr(csv_export, "query_all_metrics", fake_query_all_metrics)

    response = client.get(
        "/api/export/starlink-csv",
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": 10,
        },
    )

    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == csv_export.CSV_COLUMNS
    assert "ground_entry_latitude" in rows[0]
    assert "ground_entry_longitude" in rows[0]
    assert "ground_entry_city" in rows[0]
