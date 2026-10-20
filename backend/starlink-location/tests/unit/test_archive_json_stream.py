"""Chunked escaping retains the original persisted and fingerprint JSON format."""

import json

import pytest

from app.mission.package.json_stream import iter_json


@pytest.mark.parametrize("compact", [False, True])
def test_chunked_json_preserves_canonical_bytes_and_bounds_large_string_chunks(compact):
    value = {"z": [True, False, None, 1.25, 7], "files": {"a": '\\"\n\x00é😀' * 20000}}
    chunks = list(iter_json(value, compact=compact))
    assert max(map(len, chunks)) <= 12 * 16384
    assert "".join(chunks) == json.dumps(
        value, sort_keys=True, separators=(",", ":") if compact else (", ", ": ")
    )
