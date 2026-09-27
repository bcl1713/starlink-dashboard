"""Typed transport for bounded diagnostics retained across platform failures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NoReturn


@dataclass
class PlatformFailure(ValueError):
    """Preserve a classified cause and its bounded platform diagnostics."""

    cause: BaseException
    platform_artifacts: Mapping[str, bytes]
    platform_cleanup_error: str = ""
    build_supervision: Mapping[str, object] | None = None

    def __str__(self) -> str:
        return str(self.cause)


def raise_with_platform_metadata(
    cause: BaseException,
    *,
    artifacts: Mapping[str, bytes],
    cleanup_error: str = "",
    supervision: Mapping[str, object] | None = None,
) -> NoReturn:
    """Raise a typed carrier while preserving the primary causal exception."""
    raise PlatformFailure(
        cause,
        artifacts,
        platform_cleanup_error=cleanup_error,
        build_supervision=supervision,
    ) from cause
