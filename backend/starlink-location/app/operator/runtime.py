"""Gated, failure-isolated Operator lifecycle with no implicit initialization."""

import os
from contextlib import contextmanager
from threading import RLock

from .clock import Clock
from .errors import OperatorError
from .event_identity import ModelStability
from .event_policy import EventPolicy
from .event_publication import EventPublication, SnapshotRegistry
from .models import Actor, StoreHealth
from .references import MissionReferences
from .service import OperatorService
from .settings import OperatorSettings
from .store import OperatorStore


def namespace_status(settings):
    """Read-only distinction between a pristine namespace and recovery evidence."""
    database, marker = settings.database_path, settings.identity_path
    present = [os.path.lexists(path) for path in (database, marker)]
    if all(present):
        return "existing"
    if any(present):
        return "recovery"
    directory = database.parent
    if directory.is_symlink():
        return "recovery"
    if directory.exists():
        # The live root may also contain independent simulation namespaces.
        entries = [
            p
            for p in directory.iterdir()
            if not (
                settings.source_mode == "live"
                and p.name in ("simulation", "simulation-missions")
                and p.is_dir()
            )
        ]
        if entries:
            return "recovery"
    return "new"


class OperatorRuntime:
    def __init__(self, settings, clock, *, error_code="store_unavailable"):
        self.settings, self.clock = settings, clock
        self.service = None
        self.error_code = error_code
        # Source adapters may install their actual producer-specific policies.
        self.freshness_policies = {}
        self.event_stability = ModelStability()
        self.event_policy = EventPolicy()
        self.event_publication = EventPublication()
        self.event_snapshots = SnapshotRegistry(clock=clock)

    @classmethod
    def start(cls, settings: OperatorSettings, *, clock: Clock):
        runtime = cls(settings, clock)
        if not settings.enabled:
            return runtime
        try:
            runtime.event_policy = EventPolicy.from_env()
            status = namespace_status(settings)
            if status != "existing":
                runtime.error_code = (
                    "store_initialization_required"
                    if status == "new"
                    else "store_recovery_required"
                )
                return runtime
            store = OperatorStore.open(settings, initialize=False, clock=clock)
            runtime.service = OperatorService(
                store,
                clock=clock,
                actor=Actor(backend="restricted-access operator"),
                references=MissionReferences(),
            )
        except OperatorError as error:
            runtime.error_code = error.code
        except (ValueError, TypeError):
            runtime.error_code = "invalid_configuration"
        except Exception:  # noqa: BLE001 - optional runtime preserves baseline startup
            runtime.error_code = "store_unavailable"
        return runtime

    def provision(self, *, expected_mode, expected_run):
        """Explicit first use only. Existing namespaces are opened, never reset."""
        if not enabled(self):
            raise OperatorError("operator_disabled")
        if (expected_mode, expected_run) != (
            self.settings.source_mode,
            self.settings.simulation_run_id,
        ):
            raise OperatorError("store_context_changed")
        if (
            self.settings.source_mode == "simulation"
            and not self.settings.simulation_run_id
        ):
            raise OperatorError("simulation_run_required")
        if not self.settings.enabled or self.error_code == "invalid_configuration":
            raise OperatorError(self.error_code)
        if self.service is not None:
            state = self.health()
            if not state.ready:
                raise OperatorError(state.error_code or "store_recovery_required")
            return state
        try:
            status = namespace_status(self.settings)
            if status == "recovery":
                raise OperatorError("store_recovery_required")
            store = OperatorStore.open(
                self.settings, initialize=status == "new", clock=self.clock
            )
            self.service = OperatorService(
                store,
                clock=self.clock,
                actor=Actor(backend="restricted-access operator"),
                references=MissionReferences(),
            )
        except (OSError, ValueError) as error:
            raise OperatorError("store_unavailable") from error
        return self.health()

    def health(self) -> StoreHealth:
        if self.service is not None:
            return self.service.store.health()
        return StoreHealth(
            ready=False,
            source_mode=self.settings.source_mode,
            simulation_run_id=self.settings.simulation_run_id,
            error_code=self.error_code,
            replay_run_id=self.settings.replay_run_id,
            mission_journal=self.settings.mission_journal,
        )

    def close(self):
        adapter = getattr(self, "event_source_adapter", None)
        if callable(getattr(adapter, "close", None)):
            adapter.close()
        self.event_snapshots.clear()
        if self.service is not None:
            self.service.store.close()


class OperatorRuntimeBinding:
    """Serialize whole requests with rebind/close so namespaces never overlap."""

    def __init__(self, *, clock, context, mission_journals=False):
        self.clock, self.context = clock, context
        self.mission_journals = mission_journals
        self.lock = RLock()
        self.runtime = None
        self.identity = None

    def _resolve(self):
        mode, actual_run = self.context()
        run = (
            actual_run or os.getenv("OPERATOR_SIMULATION_RUN_ID") or None
            if mode == "simulation"
            else None
        )
        # Resolve mode/run from the actual coordinator, never source-mode env.
        enabled = os.getenv("OPERATOR_ENABLED", "false").lower() == "true"
        mission_journal = self.mission_journals and mode == "simulation"
        session = os.getenv("OPERATOR_EVALUATION_SESSION", "default")
        if mission_journal:
            # New path family: never adopt, merge or modify legacy per-run stores.
            run = session
        identity = (mode, run, enabled, actual_run if mission_journal else None)
        if identity != self.identity or (
            enabled and self.runtime is not None and self.runtime.service is None
        ):
            if self.runtime is not None:
                self.runtime.close()
            options = {
                "enabled": enabled,
                "source_mode": mode,
                "simulation_run_id": run,
                "mission_journal": mission_journal,
                "replay_run_id": actual_run if mission_journal else None,
                "root": os.getenv("OPERATOR_ROOT", "data/operator"),
            }
            try:
                settings = OperatorSettings(
                    **options,
                    capacity_bytes=int(
                        os.getenv("OPERATOR_CAPACITY_BYTES", str(1024**3))
                    ),
                    backup_count=int(os.getenv("OPERATOR_BACKUP_COUNT", "3"))
                )
                runtime = OperatorRuntime.start(settings, clock=self.clock)
            except (ValueError, TypeError):
                # Missing run/config is unavailable without touching a store.
                options["enabled"] = False
                options["simulation_run_id"] = None
                options["replay_run_id"] = None
                settings = OperatorSettings(**options)
                runtime = OperatorRuntime(
                    settings,
                    self.clock,
                    error_code=(
                        "simulation_run_required"
                        if mode == "simulation" and not run
                        else "invalid_configuration"
                    ),
                )
                runtime.enabled_override = enabled
            self.runtime, self.identity = runtime, identity
        return self.runtime

    @contextmanager
    def access(self):
        with self.lock:
            yield self._resolve()

    def close(self):
        with self.lock:
            if self.runtime is not None:
                self.runtime.close()


def enabled(runtime):
    return getattr(runtime, "enabled_override", runtime.settings.enabled)


@contextmanager
def runtime_for(request):
    binding = getattr(request.app.state, "operator_binding", None)
    if binding is not None:
        with binding.access() as runtime:
            yield runtime
    else:
        yield getattr(request.app.state, "operator_runtime", None)
