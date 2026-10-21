"""Frozen c7792320 coupled schema: test/measurement inputs, never runtime state."""

import json
from pathlib import Path

from app.core.metrics.frames import GaugeDefinition


def actual_schema():
    path = Path(__file__).resolve().parents[1] / "fixtures/metrics-coupled-schema.json"
    definitions = tuple(
        GaugeDefinition(**record) for record in json.loads(path.read_text())
    )
    assert len(definitions) == 29
    assert len({definition.name for definition in definitions}) == 29
    return definitions
