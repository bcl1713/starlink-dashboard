"""All-or-nothing loading of configurable, source-attributed PoP catalogs."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .models import PopCatalog, PopSite

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "assets/starshield-pops.json"
)


class _CatalogFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sites: tuple[PopSite, ...] = Field(min_length=1)


def load_catalog(path: Path) -> PopCatalog:
    """Reject the whole catalog on invalid entries; hash canonical validated data."""
    return parse_catalog(path.read_bytes())


def parse_catalog(content: bytes) -> PopCatalog:
    """Validate captured bytes without consulting mutable configuration or disk."""
    parsed = _CatalogFile.model_validate_json(content)
    ids, identities, locations = set(), set(), set()
    for site in parsed.sites:
        identity = (site.city.casefold(), site.country.casefold())
        # Poles and the two representations of the anti-meridian are identical.
        location = (
            site.latitude,
            0 if abs(site.latitude) == 90 else (site.longitude + 180) % 360,
        )
        if site.id in ids or identity in identities or location in locations:
            raise ValueError("Duplicate PoP ID, city/country identity, or location")
        ids.add(site.id)
        identities.add(identity)
        locations.add(location)
    sites = tuple(sorted(parsed.sites, key=lambda site: site.id))
    canonical = json.dumps(
        [site.model_dump(mode="json") for site in sites],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return PopCatalog(sites=sites, fingerprint=fingerprint)
