"""Synthetic, reproducible historical density for real Prometheus controls."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

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


def write_seed(output: Path, end_seconds: int, duration_seconds: int = 4200) -> None:
    """Emit one labeled source per metric, with dense finite zeros and spikes."""
    if duration_seconds < 1 or end_seconds < duration_seconds:
        raise ValueError("Positive duration and an end after the duration required")
    with output.open("w") as stream:
        for metric in METRICS:
            stream.write(f"# TYPE {metric} gauge\n")
            for offset in range(duration_seconds + 1):
                wave = math.sin(offset / 31)
                values = (
                    35 + wave * 0.02,
                    -100 + wave * 0.02,
                    35000 + wave * 200,
                    450 + wave * 10,
                    90 + wave,
                    40 + wave * 5,
                    60 + wave * 10,
                    10 + wave * 3,
                    0 if offset % 73 else 2,
                    0 if offset % 47 else 1,
                    100,
                )
                value = values[METRICS.index(metric)]
                if metric.endswith("latency_ms_current") and offset % 127 == 0:
                    value = 160
                timestamp = end_seconds - duration_seconds + offset
                stream.write(
                    f'{metric}{{instance="starlink-location:8000",job="starlink-location"}} {value:.8g} {timestamp}\n'
                )
        stream.write("# EOF\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--duration", type=int, default=4200)
    args = parser.parse_args()
    write_seed(args.output, args.end, args.duration)
