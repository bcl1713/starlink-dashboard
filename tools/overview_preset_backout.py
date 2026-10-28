#!/usr/bin/env python3
"""Prepare a separate pre-426-compatible settings file; never overwrite input."""

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path


def prepare_payload(payload):
    result = deepcopy(payload)
    if not isinstance(result, dict):
        raise ValueError("Settings must be a JSON object")
    result.pop("next_flight_events_only", None)
    presets = result.get("operator_presets", {})
    if not isinstance(presets, dict):
        raise ValueError("Saved presets must be an object")
    for preset in presets.values():
        if preset is None:
            continue
        if not isinstance(preset, dict) or not isinstance(preset.get("settings"), dict):
            raise ValueError("Malformed preset; preserve the original and inspect it")
        preset["settings"].pop("next_flight_events_only", None)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepared = prepare_payload(json.loads(args.input.read_text()))
    # Exclusive creation and private permissions; original and existing output stay intact.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(prepared, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
