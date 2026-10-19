"""Explicit configuration and separate live/simulation storage namespaces."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class OperatorSettings:
    enabled: bool = False
    root: Path = Path("data/operator")
    source_mode: Literal["live", "simulation"] = "live"
    simulation_run_id: str | None = None
    mission_journal: bool = False
    replay_run_id: str | None = None
    capacity_bytes: int = 1024**3
    backup_count: int = 3

    def __post_init__(self):
        object.__setattr__(self, "root", Path(self.root))
        if self.mission_journal and self.source_mode != "simulation":
            raise ValueError("Mission journal namespaces are simulation-only")
        if self.source_mode not in ("live", "simulation"):
            raise ValueError("Unknown Operator source mode")
        if self.source_mode == "simulation":
            if (self.enabled or self.simulation_run_id is not None) and (
                not self.simulation_run_id
                or not re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", self.simulation_run_id
                )
            ):
                raise ValueError("Simulation requires a safe, explicit run ID")
        elif self.simulation_run_id is not None:
            raise ValueError("Live stores cannot have a simulation run ID")
        if self.capacity_bytes < 1 or self.backup_count < 1:
            raise ValueError("Capacity and backup count must be positive")

    @property
    def database_path(self) -> Path:
        directory = self.root
        if self.source_mode == "simulation":
            if self.simulation_run_id is None:
                raise ValueError("Simulation requires an explicit run ID")
            directory = (
                directory
                / ("simulation-missions" if self.mission_journal else "simulation")
                / self.simulation_run_id
            )
        return directory / "operations.sqlite3"

    @property
    def identity_path(self) -> Path:
        return self.database_path.with_name("operations.identity.json")

    @classmethod
    def from_env(cls) -> "OperatorSettings":
        enabled = os.getenv("OPERATOR_ENABLED", "false").lower()
        if enabled not in ("true", "false"):
            raise ValueError("OPERATOR_ENABLED must be true or false")
        return cls(
            enabled=enabled == "true",
            root=Path(os.getenv("OPERATOR_ROOT", "data/operator")),
            source_mode=os.getenv(
                "OPERATOR_SOURCE_MODE", os.getenv("STARLINK_MODE", "live")
            ),
            simulation_run_id=os.getenv("OPERATOR_SIMULATION_RUN_ID") or None,
            capacity_bytes=int(os.getenv("OPERATOR_CAPACITY_BYTES", str(1024**3))),
            backup_count=int(os.getenv("OPERATOR_BACKUP_COUNT", "3")),
        )
