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


def seed_prerequisites(root, *, routes_dir=None):
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
    clock = training_clock(root)
    fixture["mission"]["name"] = "Training mission · Fictional Meridian 21"
    fixture["mission"]["legs"][0]["name"] = "First flight · Meridian to Harbor"
    fixture["mission"]["legs"][1]["name"] = "Second flight · Harbor to Meridian"
    for index, leg in enumerate(fixture["mission"]["legs"], 1):
        leg["route_id"] = f"operator-training-leg-{index}"
        leg["transports"]["initial_ka_satellite_ids"] = ["AOR"]
    later = copy.deepcopy(fixture["planned_commands"][:2])
    for index, command in enumerate(later):
        command["leg_id"] = fixture["mission"]["legs"][1]["id"]
        command["payload"]["title"] = f"Synthetic return briefing {index + 1}"
        start = _existing_clock_module().START + timedelta(minutes=65 + index * 5)
        command["time"]["planned_start_at"] = start.isoformat()
        command["time"]["planned_end_at"] = (start + timedelta(minutes=15)).isoformat()
    overdue = copy.deepcopy(fixture["planned_commands"][0])
    overdue["scope"] = "mission"
    overdue["leg_id"] = None
    overdue["payload"]["title"] = "Synthetic overdue coordination"
    overdue["payload"]["party"] = "Synthetic overdue customer"
    overdue["time"]["planned_start_at"] = (
        _existing_clock_module().START - timedelta(minutes=15)
    ).isoformat()
    overdue["time"]["planned_end_at"] = (
        _existing_clock_module().START - timedelta(minutes=5)
    ).isoformat()
    commands = fixture["planned_commands"] + later + [overdue]
    routes = (
        Path(routes_dir) if routes_dir is not None else root / "route-data" / "routes"
    )
    routes.mkdir(parents=True, exist_ok=True)
    origin = _existing_clock_module().START
    for index, leg in enumerate(fixture["mission"]["legs"]):
        path = routes / (leg["route_id"] + ".kml")
        if path.exists():
            continue
        departure = origin + timedelta(minutes=45 * index)
        longitudes = (-10, 0, 10) if index == 0 else (10, 0, -10)
        names = ("MERA", "MID", "HARB") if index == 0 else ("HARB", "MID", "MERA")
        route_name = "MERA-HARB" if index == 0 else "HARB-MERA"
        points = "".join(
            f'<Placemark><name>{name}</name><description>Time Over Waypoint: {(departure + timedelta(minutes=15 * point)).strftime("%Y-%m-%d %H:%M:%SZ")}</description><Point><altitudeMode>clampToGround</altitudeMode><coordinates>{longitude},0</coordinates></Point></Placemark>'
            for point, (name, longitude) in enumerate(zip(names, longitudes))
        )
        coordinates = " ".join(f"{longitude},0" for longitude in longitudes)
        path.write_text(
            f'<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fictional {route_name} training leg {index + 1}</name><Placemark><name>Route</name><LineString><altitudeMode>clampToGround</altitudeMode><coordinates>{coordinates}</coordinates></LineString></Placemark>{points}</Document></kml>'
        )
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
        mission = storage.load_mission_v2(fixture["mission"]["id"])
        metadata = {
            "version": 1,
            "namespace": namespace,
            "prerequisite_record_ids": record_ids,
        }
        existing_metadata = mission.metadata.get("operator_training_fixture")
        if existing_metadata is not None and existing_metadata != metadata:
            raise ValueError(
                "Training mission marker mismatch; preserve existing mission"
            )
        if existing_metadata is None:
            mission.metadata["operator_training_fixture"] = metadata
            storage.save_mission_v2(mission)
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


CHECKPOINTS = {
    "preflight": {"minutes": 0, "longitude": -10, "speed": 0},
    "leg-one": {"minutes": 15, "longitude": -8, "speed": 600},
    "leg-one-restriction": {"minutes": 23, "longitude": 1, "speed": 600},
    "between-legs": {"minutes": 45, "longitude": 10, "speed": 0},
    "leg-two": {"minutes": 65, "longitude": 1, "speed": 600},
    "postflight": {"minutes": 80, "longitude": -10, "speed": 0},
}


def _existing_clock_module():
    import importlib.util

    source = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "operator_training_existing_clock",
        source / "tools/acceptance/operator-journal/scenario.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkpoint_inputs(root):
    training_namespace(root, mode="simulation")
    path = Path(root) / "training-inputs.json"
    if not path.exists():
        apply_checkpoint(root, "preflight")
    value = json.loads(path.read_text())
    from app.operator.time_models import utc_timestamp

    if (
        value.get("schema_version") != 1
        or value.get("checkpoint_id") not in CHECKPOINTS
    ):
        raise ValueError("Invalid persisted training inputs; preserve for recovery")
    utc_timestamp(value["now"])
    return value


def apply_checkpoint(root, checkpoint_id):
    """Persist predefined raw input and time only; never writes learner outcomes."""
    from datetime import timedelta

    from app.operator.time_models import utc_timestamp

    training_namespace(root, mode="simulation")
    if checkpoint_id not in CHECKPOINTS:
        raise ValueError("Unknown training checkpoint")
    step = CHECKPOINTS[checkpoint_id]
    now = _existing_clock_module().START + timedelta(minutes=step["minutes"])
    path = Path(root) / "training-inputs.json"
    if path.exists() and utc_timestamp(json.loads(path.read_text())["now"]) > now:
        raise ValueError(
            "Checkpoints cannot move time backwards; reset into a fresh owned root instead"
        )
    value = {
        "schema_version": 1,
        "checkpoint_id": checkpoint_id,
        "now": now.isoformat(),
        "latitude": 0,
        "longitude": step["longitude"],
        "speed": step["speed"],
        "heading": 270 if checkpoint_id in ("leg-two", "postflight") else 90,
        "stale": False,
        "invalid_ka": False,
        "missing_pop": False,
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)
    return value


def training_clock(root):
    """Reuse ScenarioClock.advance; persisted raw inputs remain the authority."""
    from app.operator.time_models import utc_timestamp

    initial = utc_timestamp(checkpoint_inputs(root)["now"])
    base = _existing_clock_module().ScenarioClock

    class TrainingClock(base):
        def set(self, value):
            value = utc_timestamp(value)
            seconds = (value - self.current).total_seconds()
            if seconds < 0:
                raise ValueError("Training clock cannot move backwards")
            self.advance(seconds)

        def _refresh(self):
            self.set(checkpoint_inputs(root)["now"])

        def now(self):
            self._refresh()
            return super().now()

        def monotonic(self):
            self._refresh()
            return super().monotonic()

    return TrainingClock(initial)
