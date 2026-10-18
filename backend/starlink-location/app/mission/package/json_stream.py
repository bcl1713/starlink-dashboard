"""Stable JSON with bounded string-escaping chunks, including large CSV members."""

import json


def iter_json(value, *, compact=False):
    comma, colon = (",", ":") if compact else (", ", ": ")
    if isinstance(value, str):
        yield '"'
        for offset in range(0, len(value), 16384):
            yield json.dumps(value[offset : offset + 16384], ensure_ascii=True)[1:-1]
        yield '"'
    elif isinstance(value, dict):
        yield "{"
        for index, key in enumerate(sorted(value)):
            if index:
                yield comma
            yield from iter_json(key, compact=compact)
            yield colon
            yield from iter_json(value[key], compact=compact)
        yield "}"
    elif isinstance(value, (list, tuple)):
        yield "["
        for index, item in enumerate(value):
            if index:
                yield comma
            yield from iter_json(item, compact=compact)
        yield "]"
    else:
        yield json.dumps(value, allow_nan=False)
