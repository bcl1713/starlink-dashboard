"""Real mission/store fixtures and command construction for service behavior."""

from uuid import uuid4

from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.operator.models import CreateRecord, UpdateRecord


def save_mission(mission_id):
    storage.save_mission_v2(
        Mission(
            id=mission_id,
            name=mission_id,
            legs=[
                MissionLeg(
                    id="leg-a",
                    name="Leg A",
                    route_id="route-a",
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
        )
    )


def submit(service, command, key=None):
    return service.execute(
        command, key=key or str(uuid4()), epoch=str(service.store.health().api_epoch)
    )


def create(service, record_data, **updates):
    return submit(
        service, CreateRecord.model_validate(record_data | updates)
    ).saved_records[0]


def update(service, saved, **updates):
    data = {
        name: getattr(saved, name)
        for name in ("record_type", "mission_id", "leg_id", "scope", "time", "payload")
    }
    return UpdateRecord(
        record_id=saved.record_id, expected_version=saved.version, **(data | updates)
    )
