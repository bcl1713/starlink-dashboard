"""Gated, failure-isolated Operator lifecycle with no implicit initialization."""

import os
from contextlib import contextmanager
from threading import RLock

from .clock import Clock
from .errors import OperatorError
from .models import Actor, StoreHealth
from .references import MissionReferences
from .service import OperatorService
from .settings import OperatorSettings
from .store import OperatorStore


class OperatorRuntime:
    def __init__(self, settings, clock, *, error_code="store_unavailable"):
        self.settings, self.clock = settings, clock
        self.service = None
        self.error_code = error_code
        # Source adapters may install their actual producer-specific policies.
        self.freshness_policies = {}

    @classmethod
    def start(cls, settings: OperatorSettings, *, clock: Clock):
        runtime = cls(settings, clock)
        if not settings.enabled:
            return runtime
        try:
            store = OperatorStore.open(settings, initialize=False, clock=clock)
            runtime.service = OperatorService(
                store,
                clock=clock,
                actor=Actor(backend="restricted-access operator"),
                references=MissionReferences(),
            )
        except OperatorError as error:
            runtime.error_code = error.code
        except Exception:  # noqa: BLE001 - optional runtime preserves baseline startup
            runtime.error_code = "store_unavailable"
        return runtime

    def health(self) -> StoreHealth:
        if self.service is not None:
            return self.service.store.health()
        return StoreHealth(
            ready=False,
            source_mode=self.settings.source_mode,
            simulation_run_id=self.settings.simulation_run_id,
            error_code=self.error_code,
        )

    def close(self):
        if self.service is not None:
            self.service.store.close()


class OperatorRuntimeBinding:
    """Serialize whole requests with rebind/close so namespaces never overlap."""

    def __init__(self, *, clock, context):
        self.clock, self.context = clock, context
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
        identity = (mode, run, enabled)
        if identity != self.identity:
            if self.runtime is not None:
                self.runtime.close()
            options = {
                "enabled": enabled,
                "source_mode": mode,
                "simulation_run_id": run,
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
                settings = OperatorSettings(**options)
                runtime = OperatorRuntime(settings, self.clock)
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
