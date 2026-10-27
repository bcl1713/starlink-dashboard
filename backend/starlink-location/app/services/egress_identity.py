"""Operator-supplied IPv4 identity, independent of provider geography."""

from dataclasses import dataclass
from functools import lru_cache
from ipaddress import IPv4Address, IPv4Network


@dataclass(frozen=True, slots=True)
class EgressIdentity:
    pop_id: str
    matched_cidr: str
    city: str
    country: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...] = ()


_PREFIXES = (
    (IPv4Network("216.255.176.0/24"), "los-angeles"),
    (IPv4Network("216.255.182.0/24"), "los-angeles"),
    (IPv4Network("216.255.177.0/24"), "ashburn"),
    (IPv4Network("216.255.183.0/24"), "ashburn"),
    (IPv4Network("216.255.178.0/24"), "dallas"),
    (IPv4Network("75.78.128.0/24"), "dallas"),
    (IPv4Network("216.255.179.0/24"), "sydney"),
    (IPv4Network("216.255.180.0/24"), "frankfurt"),
    (IPv4Network("216.255.181.0/24"), "tokyo"),
)


@lru_cache(maxsize=1)
def _catalog_sites():
    # Pop models reference GroundEntryPoint, so load only after module setup.
    from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog

    return {site.id: site for site in load_catalog(DEFAULT_CATALOG_PATH).sites}


def resolve_egress_identity(ip: str) -> EgressIdentity | None:
    """Match exact supplied CIDRs; coordinates always come from the catalog."""
    try:
        address = IPv4Address(ip)
    except (ValueError, TypeError):
        return None
    for network, pop_id in _PREFIXES:
        if address in network:
            site = _catalog_sites()[pop_id]
            return EgressIdentity(
                pop_id=pop_id,
                matched_cidr=str(network),
                city=site.city,
                country=site.country,
                latitude=site.latitude,
                longitude=site.longitude,
                aliases=site.aliases,
            )
    return None
