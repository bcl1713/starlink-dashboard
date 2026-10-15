"""Disposable geometry process; cap resources before importing Shapely."""

import json
import os
import resource
import sys

MAX_INPUT_BYTES = 32 * 1024**2
MAX_OUTPUT_BYTES = 8 * 1024**2


def main():
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    from .route_geometry import intersect_route

    body = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(body) > MAX_INPUT_BYTES:
        raise ValueError("worker input limit")
    payload = json.loads(body)
    result = intersect_route(payload["points"], payload["collection"]["features"])
    encoded = result.model_dump_json().encode()
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ValueError("worker output limit")
    sys.stdout.buffer.write(encoded)


if __name__ == "__main__":
    main()
