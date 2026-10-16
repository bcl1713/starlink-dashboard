"""Bounded raw range-vector recovery; query evaluation times are not observations."""

import json
import os
from datetime import datetime, timezone
from math import isfinite

import httpx

from app.services.telemetry_archive.store import METRICS


class ArchiveReader:
    def __init__(
        self,
        client: httpx.Client,
        *,
        instance: str | None = None,
        job: str | None = None,
    ):
        self.client = client
        self.instance = instance or os.getenv(
            "FLIGHT_ARCHIVE_PROMETHEUS_INSTANCE", "starlink-location:8000"
        )
        self.job = job or os.getenv(
            "FLIGHT_ARCHIVE_PROMETHEUS_JOB", "starlink-location"
        )

    def read(self, start: datetime, end: datetime):
        duration = max(1, int((end - start).total_seconds()) + 1)
        if duration > 301:
            raise ValueError("Archive query chunk exceeds five minutes")
        names = "|".join((*METRICS, "starlink_mode_info"))
        response = self.client.get(
            "/api/v1/query",
            params={
                "query": f'{{__name__=~"{names}",instance={json.dumps(self.instance)},job={json.dumps(self.job)}}}[{duration}s]',
                "time": str(end.timestamp()),
            },
        )
        response.raise_for_status()
        payload = response.json()
        if (
            payload.get("status") != "success"
            or payload.get("data", {}).get("resultType") != "matrix"
        ):
            raise ValueError("Prometheus archive query did not return raw samples")
        series = [
            item
            for item in payload["data"]["result"]
            if item.get("metric", {}).get("instance") == self.instance
            and item.get("metric", {}).get("job") == self.job
        ]
        live = set()
        other = set()
        for item in series:
            labels = item.get("metric", {})
            if labels.get("__name__") == "starlink_mode_info":
                identity = (labels.get("instance"), labels.get("job"))
                for stamp, value in item.get("values", []):
                    if float(value) == 1:
                        target = live if labels.get("mode") == "live" else other
                        target.add((float(stamp), identity))
        rows = []
        for item in series:
            labels = item.get("metric", {})
            metric = labels.get("__name__")
            if metric not in METRICS:
                continue
            identity = (labels.get("instance"), labels.get("job"))
            for stamp, value in item.get("values", []):
                stamp = float(stamp)
                key = (stamp, identity)
                if (
                    key not in live
                    or key in other
                    or not start.timestamp() <= stamp <= end.timestamp()
                ):
                    continue
                number = float(value)
                rows.append(
                    (
                        datetime.fromtimestamp(stamp, timezone.utc),
                        metric,
                        {key: val for key, val in labels.items() if key != "__name__"}
                        | {"source": "prometheus_raw_scrape"},
                        number if isfinite(number) else None,
                        "live",
                        None,
                    )
                )
        return rows
