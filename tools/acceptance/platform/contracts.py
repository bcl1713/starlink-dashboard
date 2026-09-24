"""Strict parsing for product-only acceptance contracts."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import tomllib

from .model import ProductContract, RuntimeControl, StaticGroup

_TOP_LEVEL = frozenset(
    {"name", "services", "static_groups", "controls", "journey_adapter", "assets"}
)
_OPERATIONAL_TOKENS = (
    "browser",
    "chrome",
    "playwright",
    "npm",
    "npx",
    "package_manager",
    "install",
    "docker",
    "compose",
    "timeout",
    "xvfb",
    "cdp",
    "evidence",
    "retry",
    "cleanup",
)
_COMMAND_PREFIXES = frozenset(
    {
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "pip",
        "uv",
        "poetry",
        "bun",
        "docker",
        "docker-compose",
        "compose",
    }
)
_SHELL_WRAPPERS = frozenset({"sh", "bash", "dash", "zsh"})


def load_product_contract(path: Path) -> ProductContract:
    """Load a TOML product contract without granting platform authority."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"invalid product contract: {error}") from error
    unknown = set(raw) - _TOP_LEVEL
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown top-level contract section(s): {names}")
    _reject_operational_keys(raw)
    return _parse_product_contract(raw)


def _reject_operational_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError("contract keys must be strings")
            normalized = key.lower().replace("-", "_")
            if any(token in normalized for token in _OPERATIONAL_TOKENS):
                raise ValueError(f"{key} is platform-owned operational authority")
            _reject_operational_keys(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_operational_keys(item)


def _parse_product_contract(raw: Mapping[str, Any]) -> ProductContract:
    unknown = set(raw) - _TOP_LEVEL
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown top-level contract section(s): {names}")
    name = _nonempty_string(raw.get("name"), "name")
    services = _unique_strings(raw.get("services"), "services")
    static_groups = tuple(
        _parse_static_group(item) for item in _tables(raw, "static_groups")
    )
    controls = tuple(_parse_control(item) for item in _tables(raw, "controls"))
    assets = tuple(
        _repository_path(item, "assets")
        for item in _strings(raw.get("assets"), "assets")
    )
    if not static_groups or not controls or not assets:
        raise ValueError("static_groups, controls, and assets must not be empty")
    if len({group.name for group in static_groups}) != len(static_groups):
        raise ValueError("static group names must be unique")
    if len({control.name for control in controls}) != len(controls):
        raise ValueError("control names must be unique")
    return ProductContract(
        name=name,
        services=services,
        static_groups=static_groups,
        controls=controls,
        journey_adapter=_repository_path(raw.get("journey_adapter"), "journey_adapter"),
        assets=assets,
    )


def _parse_static_group(raw: Mapping[str, Any]) -> StaticGroup:
    _require_keys(raw, {"name", "working_directory", "commands"}, "static group")
    commands = _unique_strings(raw.get("commands"), "static group commands")
    if any(_is_operational_command(command) for command in commands):
        raise ValueError(
            "static group commands are platform-owned operational authority"
        )
    return StaticGroup(
        name=_nonempty_string(raw.get("name"), "static group name"),
        working_directory=_repository_path(
            raw.get("working_directory"), "working_directory"
        ),
        commands=commands,
    )


def _parse_control(raw: Mapping[str, Any]) -> RuntimeControl:
    _require_keys(raw, {"name", "path", "expected_status"}, "control")
    path = _nonempty_string(raw.get("path"), "control path")
    status = raw.get("expected_status")
    if (
        not path.startswith("/")
        or not isinstance(status, int)
        or not 100 <= status <= 599
    ):
        raise ValueError("control path and expected_status are invalid")
    return RuntimeControl(
        _nonempty_string(raw.get("name"), "control name"), path, status
    )


def _is_operational_command(command: str) -> bool:
    try:
        words = shlex.split(command)
    except ValueError:
        return True
    if not words:
        return True
    if any(word in _COMMAND_PREFIXES or word == "install" for word in words):
        return True
    return any(
        _is_operational_command(words[index + 1])
        for index, word in enumerate(words[:-1])
        if word == "-c" and index and words[index - 1] in _SHELL_WRAPPERS
    )


def _tables(raw: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    value = raw.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, Mapping) for item in value
    ):
        raise ValueError(f"{field} must be an array of tables")
    return list(value)


def _strings(value: object, field: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ValueError(f"{field} must be a non-empty string list")
    return list(value)


def _unique_strings(value: object, field: str) -> tuple[str, ...]:
    items = _strings(value, field)
    if len(set(items)) != len(items):
        raise ValueError(f"{field} must not contain duplicates")
    return tuple(items)


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    return value


def _repository_path(value: object, field: str) -> Path:
    item = _nonempty_string(value, field)
    path = Path(item)
    backslash_parts = item.split("\\")
    if (
        path.is_absolute()
        or item.startswith("\\")
        or (len(item) >= 2 and item[0].isalpha() and item[1] == ":")
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(part in {"", ".", ".."} for part in backslash_parts)
    ):
        raise ValueError(f"{field} must be a contained repository-relative path")
    return path


def _require_keys(raw: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise ValueError(f"{label} has unknown or missing fields")
