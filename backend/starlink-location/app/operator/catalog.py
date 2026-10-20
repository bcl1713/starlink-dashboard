"""Installation-wide reusable catalogs; journal rows retain display-name snapshots."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from pydantic import Field, field_validator, model_validator

from .common import Identifier, StrictModel
from .errors import OperatorError


class CatalogItem(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    archived: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()


class Catalog(StrictModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    version: int = Field(default=0, ge=0)
    services: list[CatalogItem] = Field(default_factory=list, max_length=500)
    transports: list[CatalogItem] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_entries(self):
        for items in (self.services, self.transports):
            if len({i.id for i in items}) != len(items) or len(
                {i.name.casefold() for i in items}
            ) != len(items):
                raise ValueError("Catalog IDs and names must be unique")
        return self


def defaults():
    return Catalog(
        services=[
            CatalogItem(id=f"service-{key}", name=name)
            for key, name in [
                ("voice", "Secure Voice"),
                ("vtc", "VTC"),
                ("iptv", "IPTV"),
                ("sipr", "SIPR Data"),
            ]
        ],
        transports=[
            CatalogItem(id=key, name=name)
            for key, name in [
                ("Starshield", "Starshield"),
                ("Ka", "Ka-band"),
                ("X", "X-band"),
            ]
        ],
    )


class CatalogStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(f"{path}.lock", timeout=5)

    def read(self):
        with self.lock:
            return (
                Catalog.model_validate_json(self.path.read_text())
                if self.path.exists()
                else defaults()
            )

    def update(self, proposed: Catalog):
        proposed = Catalog.model_validate(proposed.model_dump())
        with self.lock:
            current = self.read()
            if proposed.version != current.version:
                # Exact retry of an accepted update is harmless.
                if proposed.model_copy(update={"version": current.version}) == current:
                    return current
                raise OperatorError("version_conflict", current_version=current.version)
            for kind in ("services", "transports"):
                if not {i.id for i in getattr(current, kind)} <= {
                    i.id for i in getattr(proposed, kind)
                }:
                    raise OperatorError(
                        "validation_error",
                        fields={kind: "Archive entries instead of removing IDs"},
                    )
            saved = proposed.model_copy(update={"version": current.version + 1})
            fd, temporary = tempfile.mkstemp(
                dir=self.path.parent, prefix=".catalog-", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w") as handle:
                    json.dump(saved.model_dump(), handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return saved


@contextmanager
def assignment_guard(settings, command):
    """Validate new catalog-linked reports, holding configuration through acceptance."""
    if command.operation != "create" or command.record_type != "transport_decision":
        yield
        return
    rows = command.payload.services
    if not any(
        row.service_id or (row.applied and row.applied.transport_id) for row in rows
    ):
        yield
        return
    store = CatalogStore(settings.root / "transport-catalog.json")
    with store.lock:
        catalog = store.read()
        for row in rows:
            references = [("services", row.service_id, row.service)]
            if row.applied:
                references.append(
                    ("transports", row.applied.transport_id, row.applied.transport)
                )
            for kind, identifier, name in references:
                if identifier is None:
                    continue
                item = next(
                    (item for item in getattr(catalog, kind) if item.id == identifier),
                    None,
                )
                if (
                    item is None
                    or item.archived
                    or not item.enabled
                    or item.name != name
                ):
                    raise OperatorError(
                        "validation_error",
                        fields={
                            "catalog": "Catalog changed; refresh choices before applying"
                        },
                    )
        yield
