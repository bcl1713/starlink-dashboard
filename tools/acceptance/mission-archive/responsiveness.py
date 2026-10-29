"""Poll real status and Prometheus handlers through the production Nginx path."""

import json
import math
import time
from urllib.request import urlopen

GAUGES = (
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_altitude_feet",
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
)


def dashboard(origin):
    started = time.monotonic()
    with urlopen(origin + "/api/status", timeout=3) as response:
        status = json.load(response)
    # Only the synthetic fixture exposes this alias; it invokes the production
    # /metrics handler and collector without substituting metric values.
    with urlopen(origin + "/api/_synthetic/export-metrics", timeout=3) as response:
        text = response.read().decode()
    values = {}
    for line in text.splitlines():
        if line.startswith(GAUGES):
            name, value, *_ = line.split()
            values[name] = math.isfinite(float(value))
    assert values and status["metric_availability"]
    return {
        "seconds": time.monotonic() - started,
        "available": {name for name, available in values.items() if available},
        "status_available": {
            name
            for name, available in status["metric_availability"].items()
            if available
        },
    }
