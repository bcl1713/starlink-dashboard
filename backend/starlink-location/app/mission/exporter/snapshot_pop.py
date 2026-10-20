"""Captured PoP catalog bytes and identity; workers never consult live settings."""

from hashlib import sha256

from app.services.pop.catalog import parse_catalog

from .snapshot_inputs import SourcePayload, canonical_json


def configured_catalog_bytes():
    from app.core.config import ConfigManager

    path = ConfigManager().get_config().pop.catalog_path
    try:
        return str(path), path.read_bytes()
    except OSError:
        return str(path), None


def catalog_dependency_token():
    path, content = configured_catalog_bytes()
    return path, sha256(content).hexdigest() if content is not None else None


def capture_pop_catalog():
    _, content = configured_catalog_bytes()
    fingerprint, status = "", "unavailable"
    if content is not None:
        try:
            fingerprint = parse_catalog(content).fingerprint
            status = "ready"
        except (ValueError, TypeError):
            pass
    return (
        SourcePayload("pop_catalog", content if content is not None else b"null"),
        SourcePayload(
            "pop_catalog_identity",
            canonical_json({"fingerprint": fingerprint, "status": status}),
        ),
    )


def captured_pop_catalog(sources):
    import json

    payloads = {p.name: p.content for p in sources}
    content = payloads.get("pop_catalog", b"null")
    identity = json.loads(payloads.get("pop_catalog_identity", b"null"))
    if content == b"null" or not identity or identity["status"] != "ready":
        return None
    catalog = parse_catalog(content)
    if catalog.fingerprint != identity["fingerprint"]:
        raise ValueError("Captured PoP catalog identity mismatch")
    return catalog
