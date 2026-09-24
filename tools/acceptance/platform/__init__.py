"""Generic acceptance platform contracts and capability boundaries."""

from .contracts import load_product_contract
from .health import HealthFingerprint, run_platform_health, validate_fingerprint
from .model import (
    BuildLedgerKey,
    Lane,
    Outcome,
    PlatformProfile,
    ProductContract,
    RunResult,
)

__all__ = [
    "BuildLedgerKey",
    "HealthFingerprint",
    "Lane",
    "Outcome",
    "PlatformProfile",
    "ProductContract",
    "RunResult",
    "load_product_contract",
    "run_platform_health",
    "validate_fingerprint",
]
