"""Explicit, private training identity; normal runtime policy is untouched."""

import json
from pathlib import Path
from uuid import UUID, uuid4

MARKER = ".operator-training-root.json"
VERSION = 1


def _checked_path(root):
    root = Path(root).absolute()
    if root.is_symlink() or any(parent.is_symlink() for parent in root.parents):
        raise ValueError("Training root must not be a symlink")
    if root == Path("/"):
        raise ValueError("Training root must be a private empty directory")
    return root


def training_namespace(root, *, mode):
    if mode != "simulation":
        raise ValueError("Training requires simulation mode")
    root = _checked_path(root)
    try:
        marker = json.loads((root / MARKER).read_text())
        token = str(UUID(marker["root_id"]))
        if marker != {
            "schema_version": VERSION,
            "purpose": "operator-training",
            "root_id": token,
            "namespace": "operator-training-v1-" + token,
        }:
            raise ValueError("Invalid training marker")
        return marker["namespace"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError(
            "Explicit marked nonproduction training root required"
        ) from error


def mark_root(root):
    root = _checked_path(root)
    if (root / MARKER).exists():
        training_namespace(root, mode="simulation")
        return json.loads((root / MARKER).read_text())
    if root.exists() and any(root.iterdir()):
        raise ValueError(
            "New training root must be empty; existing data is never adopted"
        )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    token = str(uuid4())
    marker = {
        "schema_version": VERSION,
        "purpose": "operator-training",
        "root_id": token,
        "namespace": "operator-training-v1-" + token,
    }
    with (root / MARKER).open("x") as handle:
        json.dump(marker, handle, indent=2)
    return marker


def stable_context(root, current_context):
    """Fixture-only adapter: replay segment IDs do not change the learner journal."""
    namespace = training_namespace(root, mode="simulation")

    def context():
        mode, _actual_segment = current_context()
        if mode != "simulation":
            raise ValueError("Training requires simulation mode")
        return mode, namespace

    return context


def seed_prerequisites(root):
    """Create only fictional itinerary and planned requirements, idempotently."""
    import copy
    import importlib.util
    from datetime import timedelta
    from uuid import NAMESPACE_URL, uuid5

    from app.mission import storage
    from app.mission.models import Mission
    from app.operator.models import Actor, CreateRecord, RecordFilter
    from app.operator.references import MissionReferences
    from app.operator.runtime import namespace_status
    from app.operator.service import OperatorService
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore

    root = _checked_path(root)
    namespace = training_namespace(root, mode="simulation")
    source = Path(__file__).resolve().parents[3]

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, source / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    fixture = load(
        "training_workspace_inputs", "tools/acceptance/operator-workspace/fixtures.py"
    ).build_workspace_fixture("busy")
    clock = load(
        "training_existing_clock", "tools/acceptance/operator-journal/scenario.py"
    ).ScenarioClock()
    fixture["mission"]["name"] = "Training mission · Fictional Meridian 21"
    fixture["mission"]["legs"][0]["name"] = "First flight · Meridian to Harbor"
    fixture["mission"]["legs"][1]["name"] = "Second flight · Harbor to Meridian"
    for index, leg in enumerate(fixture["mission"]["legs"], 1):
        leg["route_id"] = f"operator-training-leg-{index}"
    later = copy.deepcopy(fixture["planned_commands"][:2])
    for index, command in enumerate(later):
        command["leg_id"] = fixture["mission"]["legs"][1]["id"]
        command["payload"]["title"] = f"Synthetic return briefing {index + 1}"
        start = clock.now() + timedelta(minutes=65 + index * 5)
        command["time"]["planned_start_at"] = start.isoformat()
        command["time"]["planned_end_at"] = (start + timedelta(minutes=15)).isoformat()
    commands = fixture["planned_commands"] + later
    previous = storage.MISSIONS_DIR
    storage.MISSIONS_DIR = root / "missions"
    settings = OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode="simulation",
        simulation_run_id=namespace,
    )
    store = None
    try:
        if storage.load_mission_v2(fixture["mission"]["id"]) is None:
            storage.save_mission_v2(Mission.model_validate(fixture["mission"]))
        status = namespace_status(settings)
        if status == "recovery":
            raise ValueError(
                "Training store requires recovery; never reset automatically"
            )
        store = OperatorStore.open(settings, initialize=status == "new", clock=clock)
        service = OperatorService(
            store,
            clock=clock,
            actor=Actor(backend="synthetic training prerequisites"),
            references=MissionReferences(),
        )
        record_ids = []
        epoch = str(store.health().api_epoch)
        for index, command in enumerate(commands):
            receipt = service.execute(
                CreateRecord.model_validate(command),
                key=str(uuid5(NAMESPACE_URL, f"{namespace}/planned/{index}")),
                epoch=epoch,
            )
            record_ids.extend(str(record.record_id) for record in receipt.saved_records)
        health = store.health()
        return {
            "schema_version": 1,
            "namespace": namespace,
            "mission_id": fixture["mission"]["id"],
            "leg_ids": [leg["id"] for leg in fixture["mission"]["legs"]],
            "record_ids": record_ids,
            "store_id": str(health.store_id),
            "api_epoch": str(health.api_epoch),
            "H": service.list(RecordFilter(mission_id=fixture["mission"]["id"])).H,
            "learner_actions_seeded": False,
        }
    finally:
        if store is not None:
            store.close()
        storage.MISSIONS_DIR = previous
