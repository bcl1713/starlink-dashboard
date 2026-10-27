"""Private immutable selection cache over durable v2 mission storage.

The repository gate owns all state here. There is no callback, extra lock, or watcher. Reconciliation is bounded to once
per second unless an admitted local mutation invalidates it. A lifespan owner
reconciles on an executor worker; live ticks only read the accepted snapshot.
"""

import logging
import os
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from time import monotonic

from app.mission import storage
from app.services.metrics_changes import mission_metrics_changes

logger = logging.getLogger(__name__)
RECONCILE_SECONDS = 1.0
MAX_RECONCILIATION_AGE_SECONDS = 3.0


@dataclass(frozen=True)
class LegIdentity:
    id: str


@dataclass(frozen=True)
class LiveMissionBinding:
    parent_mission_id: str
    leg: LegIdentity
    route_id: str
    route: object  # Accepted RouteManager-owned object, read only here.


@dataclass(frozen=True)
class ActiveMissionSnapshot:
    state: str
    generation: int
    mission_json: bytes | None = None
    mission_identity: str | None = None
    binding: LiveMissionBinding | None = None
    route_identity: str | None = None


@dataclass(frozen=True)
class _Selection:
    state: str
    mission_json: bytes | None = None
    mission_identity: str | None = None
    mission_id: str | None = None
    leg_id: str | None = None
    route_id: str | None = None


def _inventory(root: Path):
    """Stat membership and saved inputs, excluding timelines/exports/locks.

    Nanosecond mtime/ctime, inode and size detect in-place writes, atomic
    replacements, deletion and same-size edits. A second inventory after parsing
    rejects concurrent uncoordinated edits. Pending journals fail closed.
    """
    records = []
    for directory in sorted(root.iterdir()):
        if directory.name.startswith(".") or not directory.is_dir():
            continue
        metadata = directory / "mission.json"
        if not metadata.exists():
            continue
        paths = [metadata]
        legs = directory / "legs"
        if legs.exists():
            paths.extend(storage._iter_mission_leg_files(legs))
        for path in paths:
            stat = path.stat()
            records.append(
                (
                    str(path.relative_to(root)),
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                )
            )
    journals = root / ".planning" / "journals"
    if journals.exists() and any(journals.glob("*.json")):
        raise RuntimeError("Planning recovery required before context resolution")
    return tuple(records)


def _selection(inventory):
    active = []
    seen = set()
    for path, *_ in inventory:
        if not path.endswith("/mission.json"):
            continue
        directory_id = Path(path).parts[0]
        mission = storage.load_mission_v2(directory_id)
        if mission is None or mission.id != directory_id or mission.id in seen:
            raise ValueError("Missing or duplicate mission identity")
        seen.add(mission.id)
        active.extend((mission, leg) for leg in mission.legs if leg.is_active)
    if not active:
        return _Selection("no_active_mission")
    if len(active) != 1:
        logger.warning(
            "Conflicting active mission legs: count=%s identities=%s",
            len(active),
            [(m.id, l.id) for m, l in active[:10]],
        )
        return _Selection("inconsistent_active_mission")
    mission, leg = active[0]
    record = mission.model_dump_json().encode()
    return _Selection(
        "available",
        record,
        sha256(record).hexdigest(),
        mission.id,
        leg.id,
        leg.route_id,
    )


class ActiveContextCache:
    def __init__(self, root):
        self.root = root
        self.process_id = os.getpid()
        self.inventory = None
        self.local_generation = -1
        self.deadline = 0.0
        self.failure = None
        self.last_checked = 0.0
        self.selection = _Selection("inconsistent_active_mission")
        self.snapshot = ActiveMissionSnapshot("inconsistent_active_mission", 0)

    def reconcile(self):
        now = monotonic()
        local = mission_metrics_changes.generation
        if local == self.local_generation and now < self.deadline:
            return
        try:
            inventory = _inventory(self.root)
            if inventory != self.inventory or local != self.local_generation:
                selection = _selection(inventory)
                if _inventory(self.root) != inventory:
                    raise OSError("Mission inputs changed during reconciliation")
                self.selection = selection
            self.inventory = inventory
            self.local_generation = local
            self.deadline = now + RECONCILE_SECONDS
            self.failure = None
            self.last_checked = monotonic()
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            # Discard the previous source, and throttle failed reconciliation
            # too: persistent corrupt files must not restore per-tick scans.
            self.inventory = None
            self.local_generation = local
            self.deadline = now + RECONCILE_SECONDS
            self.selection = _Selection("inconsistent_active_mission")
            failure = (type(exc).__name__, str(exc))
            if failure != self.failure:
                logger.warning("Active mission reconciliation failed: %s", exc)
            self.failure = failure

    def read(self, manager, *, reconcile):
        if reconcile:
            self.reconcile()
        elif self.local_generation != mission_metrics_changes.generation:
            return None
        owner = getattr(manager, "_active_mission_context_owner", None)
        if (
            not reconcile
            and owner
            and monotonic() - self.last_checked > MAX_RECONCILIATION_AGE_SECONDS
        ):
            # A stalled executor must not silently extend external-edit freshness.
            return None
        selected = self.selection
        binding = None
        route_identity = None
        state = selected.state
        if state == "available":
            route_id = selected.route_id
            route = (
                manager.get_route(route_id)
                if route_id and not route_id.isspace()
                else None
            )
            if (
                route is None
                or manager.get_active_route_id() != route_id
                or manager.get_active_route() is not route
            ):
                state = "route_unavailable"
            else:
                binding = LiveMissionBinding(
                    selected.mission_id, LegIdentity(selected.leg_id), route_id, route
                )
                previous = self.snapshot.binding
                if previous is not None and previous.route is route:
                    route_identity = self.snapshot.route_identity
                else:
                    from app.core.metrics.source_admission import route_source_identity

                    route_identity = route_source_identity(route)
        candidate = ActiveMissionSnapshot(
            state,
            self.snapshot.generation,
            selected.mission_json,
            selected.mission_identity,
            binding,
            route_identity,
        )
        old = self.snapshot
        # Route models are mutable (actual flight timing advances); compare the
        # accepted object identity rather than Pydantic's deep value equality.
        key = lambda value: (
            value.state,
            value.mission_json,
            value.route_identity,
            id(value.binding.route) if value.binding else None,
        )
        if key(candidate) != key(old):
            candidate = replace(candidate, generation=old.generation + 1)
            if candidate.state != "available":
                logger.warning(
                    "Active mission context unavailable: state=%s generation=%s",
                    candidate.state,
                    candidate.generation,
                )
            else:
                logger.info(
                    "Active mission context accepted: mission=%s leg=%s generation=%s",
                    binding.parent_mission_id,
                    binding.leg.id,
                    candidate.generation,
                )
            self.snapshot = candidate
        return self.snapshot


def get_active_mission_snapshot(manager, *, reconcile=True):
    """Caller receives immutable bytes/IDs; no retained mutable mission models."""
    with storage.get_active_leg_lock():
        root = storage.MISSIONS_DIR
        cache = getattr(manager, "_active_mission_context_cache", None)
        if (
            not isinstance(cache, ActiveContextCache)
            or cache.root != root
            or cache.process_id != os.getpid()
        ):
            cache = ActiveContextCache(root)
            manager._active_mission_context_cache = cache
        return cache.read(manager, reconcile=reconcile)


def active_mission_snapshot_is_current(manager, snapshot):
    current = get_active_mission_snapshot(manager, reconcile=False)
    return current is not None and current is snapshot
