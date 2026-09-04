"""Preflight counting for bounded Prometheus matrix sample arrays."""


def count_values_items(body: bytes, limit: int) -> int:
    """Count matrix ``values`` entries without decoding their object graph."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid history encoding") from exc
    marker = '"values"'
    offset = 0
    total = 0
    found = 0
    while True:
        key = text.find(marker, offset)
        if key < 0:
            break
        cursor = _skip_space(text, key + len(marker))
        if cursor >= len(text) or text[cursor] != ":":
            offset = key + len(marker)
            continue
        cursor = _skip_space(text, cursor + 1)
        if cursor >= len(text) or text[cursor] != "[":
            raise ValueError("invalid history samples")
        count, offset = _count_array(text, cursor, limit - total)
        found += 1
        total += count
        if total > limit:
            raise ValueError("history point budget exceeded")
    if found != 1:
        raise ValueError("invalid history samples")
    return total


def _skip_space(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _count_array(text: str, start: int, remaining: int) -> tuple[int, int]:
    cursor = _skip_space(text, start + 1)
    if cursor < len(text) and text[cursor] == "]":
        return 0, cursor + 1
    count = 0
    while cursor < len(text):
        cursor = _skip_value(text, cursor)
        count += 1
        if count > remaining:
            raise ValueError("history point budget exceeded")
        cursor = _skip_space(text, cursor)
        if cursor >= len(text):
            break
        if text[cursor] == "]":
            return count, cursor + 1
        if text[cursor] != ",":
            raise ValueError("invalid history samples")
        cursor = _skip_space(text, cursor + 1)
    raise ValueError("invalid history samples")


def _skip_value(text: str, cursor: int) -> int:
    if cursor >= len(text):
        raise ValueError("invalid history samples")
    if text[cursor] == '"':
        return _skip_string(text, cursor)
    if text[cursor] in "[{":
        return _skip_nested(text, cursor)
    while cursor < len(text) and text[cursor] not in ",]}":
        cursor += 1
    return cursor


def _skip_string(text: str, cursor: int) -> int:
    cursor += 1
    escaped = False
    while cursor < len(text):
        char = text[cursor]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return cursor + 1
        cursor += 1
    raise ValueError("invalid history samples")


def _skip_nested(text: str, cursor: int) -> int:
    pairs = {"[": "]", "{": "}"}
    stack = [pairs[text[cursor]]]
    cursor += 1
    while cursor < len(text) and stack:
        char = text[cursor]
        if char == '"':
            cursor = _skip_string(text, cursor)
            continue
        if char in pairs:
            stack.append(pairs[char])
        elif char == stack[-1]:
            stack.pop()
        cursor += 1
    if stack:
        raise ValueError("invalid history samples")
    return cursor
