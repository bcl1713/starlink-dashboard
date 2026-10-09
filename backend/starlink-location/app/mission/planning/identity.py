"""Content identities independent of route/source storage remapping."""

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


def _canonical(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, Enum):
        return _canonical(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Identity timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and _TIMESTAMP.match(value):
        return _canonical(datetime.fromisoformat(value.replace("Z", "+00:00")))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Identity numbers must be finite")
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        # Binding/anchor content carries a hash; resource IDs are storage selectors.
        ignored = (
            {"route_id", "source_id", "owned_relative_path", "filename"}
            if "content_hash" in value
            else set()
        )
        return {
            key: _canonical(item)
            for key, item in sorted(value.items())
            if key not in ignored
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ValueError(f"Unsupported planning identity value: {type(value).__name__}")


def planning_identity(inputs: dict) -> str:
    """Hash UTC-normalized, finite content while retaining ordered records.

    Callers provide the evaluation input subset or the card input subset; the
    helper never silently removes schedules, locks, confirmations or policy.
    """
    payload = json.dumps(
        _canonical(inputs), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
