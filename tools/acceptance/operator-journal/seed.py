"""Idempotent, local-only synthetic seed using real mission and Operator stores."""

import json
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.mission import storage
from app.operator.clock import Clock
from app.operator.models import Actor, RecordFilter
from app.operator.references import MissionReferences
from app.operator.service import OperatorService
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import ScenarioClock, make_demo, pop_inputs


def seed_demo(
    root: Path,
    *,
    clock: Clock,
    mode: str,
    include_shell: bool = False,
    include_timelines: bool = True,
) -> dict:
    """Seed a caller-owned root before startup, restoring global storage binding."""
    if mode not in ("simulation", "live"):
        raise ValueError("Unknown fixture mode")
    root = Path(root).resolve()
    manifest_path = root / "operator" / f"synthetic-seed-{mode}.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        seed_clock = ScenarioClock(datetime.fromisoformat(manifest["started_at"]))
    else:
        seed_clock = ScenarioClock(clock.now())
    demo = make_demo(seed_clock, include_shell=include_shell)
    settings = OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode=mode,
        simulation_run_id=demo["run_id"] if mode == "simulation" else None,
    )
    previous = storage.MISSIONS_DIR
    storage.MISSIONS_DIR = root / "missions"
    store = None
    try:
        for mission in demo["missions"]:
            if storage.load_mission_v2(mission.id) is None:
                storage.save_mission_v2(mission)
        if include_timelines:
            from app.mission.pop_continuity import attach_call_continuity

            for mission in demo["missions"]:
                for leg in mission.legs:
                    timeline = pop_inputs(seed_clock)["timeline"].model_copy(
                        update={
                            "mission_leg_id": leg.id,
                            "created_at": seed_clock.now(),
                        }
                    )
                    attach_call_continuity(timeline)
                    storage.save_mission_timeline(
                        leg.id, timeline, parent_mission_id=mission.id
                    )
        store = OperatorStore.open(settings, initialize=True, clock=clock)
        service = OperatorService(
            store,
            clock=clock,
            actor=Actor(backend="synthetic acceptance fixture"),
            references=MissionReferences(),
        )
        epoch = str(store.health().api_epoch)
        records = []
        for index, command in enumerate(demo["commands"]):
            key = str(uuid5(NAMESPACE_URL, f"{demo['run_id']}/{mode}/{index}"))
            records.extend(
                str(row.record_id)
                for row in service.execute(command, key=key, epoch=epoch).saved_records
            )
        result = {
            "synthetic": True,
            "run_id": demo["run_id"],
            "source_mode": mode,
            "started_at": seed_clock.now().isoformat(),
            "record_ids": records,
            "mission_ids": [m.id for m in demo["missions"]],
            "epoch": epoch,
            "H": service.list(RecordFilter(mission_id=demo["missions"][0].id)).H,
            "roots": {
                "missions": str(root / "missions"),
                "operator": str(root / "operator"),
            },
        }
        manifest_path.write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        if store is not None:
            store.close()
        storage.MISSIONS_DIR = previous
