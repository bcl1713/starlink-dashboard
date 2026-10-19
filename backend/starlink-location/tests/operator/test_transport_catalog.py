import pytest
from pydantic import ValidationError

from app.operator.catalog import Catalog, CatalogItem, CatalogStore
from app.operator.errors import OperatorError
from app.operator.transport_models import TransportServiceRow


def test_catalog_persists_custom_choices_and_preserves_ids(tmp_path):
    store = CatalogStore(tmp_path / "catalog.json")
    initial = store.read()
    assert [i.name for i in initial.transports] == ["Starshield", "Ka-band", "X-band"]
    changed = initial.model_copy(deep=True)
    changed.services.append(CatalogItem(id="custom-service", name="Mission Data"))
    changed.transports.append(CatalogItem(id="custom-path", name="Terrestrial"))
    saved = store.update(changed)
    assert saved.version == 1
    assert CatalogStore(store.path).read() == saved
    archived = saved.model_copy(deep=True)
    archived.transports[-1].archived = True
    saved = store.update(archived)
    restored = saved.model_copy(deep=True)
    restored.transports[-1].archived = False
    assert store.update(restored).transports[-1].id == "custom-path"
    with pytest.raises(OperatorError):
        store.update(initial)
    missing = store.read()
    missing.services.pop()
    with pytest.raises(OperatorError):
        store.update(missing)


def test_duplicate_names_and_ids_rejected():
    with pytest.raises(ValidationError):
        Catalog(
            services=[
                CatalogItem(id="a", name="Voice"),
                CatalogItem(id="b", name=" voice "),
            ]
        )


def test_custom_assignment_has_stable_ids_and_historical_names():
    row = TransportServiceRow(
        row_id="11111111-1111-4111-8111-111111111111",
        service_id="service",
        service="Mission Data",
        applied={"transport": "Terrestrial", "transport_id": "path"},
    )
    assert TransportServiceRow.model_validate_json(row.model_dump_json()) == row
    assert row.applied.transport == "Terrestrial"
    assert (
        TransportServiceRow(
            row_id="22222222-2222-4222-8222-222222222222",
            service="Voice",
            applied={"transport": "X"},
        ).applied.transport
        == "X"
    )


def test_catalog_api_reuses_configuration_across_missions(api):
    base = "/api/v2/operator/transport-catalog"
    data = api.get(base).json()
    data["services"].append(
        {
            "id": "mission-data",
            "name": "Mission Data",
            "enabled": True,
            "archived": False,
        }
    )
    accepted = api.put(base, json=data)
    assert accepted.status_code == 200, accepted.text
    assert api.put(base, json=data).json() == accepted.json()
    assert api.get(base).json()["services"][-1]["id"] == "mission-data"
    conflict = data | {"services": data["services"][:-1]}
    assert api.put(base, json=conflict).status_code == 409


def test_catalog_does_not_block_pristine_store_initialization(tmp_path):
    from app.operator.runtime import namespace_status
    from app.operator.settings import OperatorSettings

    settings = OperatorSettings(enabled=True, root=tmp_path / "pristine")
    store = CatalogStore(settings.root / "transport-catalog.json")
    store.update(store.read())
    assert namespace_status(settings) == "new"


def test_legacy_transport_key_replays_after_catalog_fields_added(service, record_data):
    import hashlib
    import json
    from uuid import uuid4

    from app.operator.commands import execute_in_transaction
    from app.operator.models import CreateRecord
    from tests.operator.service_helpers import submit
    from tests.operator.test_transport_contract import decision, row

    command = CreateRecord.model_validate(
        decision(record_data, row(applied={"transport": "X"}))
    )
    body = command.model_dump(mode="json")
    for item in body["payload"]["services"]:
        item.pop("service_id", None)
        item["applied"].pop("transport_id", None)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    key = str(uuid4())
    with service.store.connect(write=True) as db:
        original = execute_in_transaction(
            db,
            command,
            key=key,
            request_hash=digest,
            clock=service.clock,
            actor=service.actor,
        )
    assert submit(service, command, key=key) == original


def test_custom_assignment_archive_preserves_history(service, record_data):
    import json

    from app.mission.package.operations_archive import journal_files
    from app.operator.models import SavedRecord
    from app.operator.projections import capture_projection
    from tests.operator.service_helpers import create, submit, update
    from tests.operator.test_transport_contract import decision, row

    catalog_store = CatalogStore(service.store.settings.root / "transport-catalog.json")
    catalog = catalog_store.read()
    catalog.services.append(CatalogItem(id="data", name="Mission Data"))
    catalog.transports.append(CatalogItem(id="path", name="Terrestrial"))
    catalog_store.update(catalog)
    first = create(
        service,
        decision(
            record_data,
            row(
                service_id="data",
                service="Mission Data",
                applied={"transport": "Terrestrial", "transport_id": "path"},
            ),
        ),
    )
    catalog = catalog_store.read()
    catalog.services[-1].name = "Renamed mission service"
    catalog.services[-1].enabled = False
    catalog.transports[-1].archived = True
    catalog_store.update(catalog)
    changed = first.payload.model_dump(mode="json")
    changed["services"][0]["applied"] = {
        "transport": "Starshield",
        "transport_id": "Starshield",
    }
    submit(service, update(service, first, payload=changed))
    files = journal_files(
        capture_projection(service.store, mission_id="demo-mission", include_audit=True)
    )
    revisions = [
        SavedRecord.model_validate_json(line)
        for line in files["operations/audit.jsonl"].splitlines()
    ]
    assert revisions[0].payload.services[0].service == "Mission Data"
    assert revisions[0].payload.services[0].applied.transport == "Terrestrial"
    assert revisions[1].payload.services[0].applied.transport_id == "Starshield"
    assert (
        json.loads(revisions[0].model_dump_json())["payload"]["services"][0][
            "service_id"
        ]
        == "data"
    )


def test_stale_catalog_assignment_rejected_but_exact_retry_preserved(
    service, record_data
):
    from uuid import uuid4

    from app.operator.models import CreateRecord
    from tests.operator.service_helpers import submit
    from tests.operator.test_transport_contract import decision, row

    command = CreateRecord.model_validate(
        decision(
            record_data,
            row(
                service_id="service-voice",
                service="Secure Voice",
                applied={"transport_id": "X", "transport": "X-band"},
            ),
        )
    )
    key = str(uuid4())
    first = submit(service, command, key=key)
    store = CatalogStore(service.store.settings.root / "transport-catalog.json")
    catalog = store.read()
    catalog.transports[-1].archived = True
    store.update(catalog)
    assert submit(service, command, key=key) == first
    with pytest.raises(OperatorError, match="validation_error"):
        submit(service, command)
