"""Label captured egress evidence explicitly as a snapshot, not leg history."""

from app.services.ground_entry_point import GroundEntryPoint

_PREFIX = "Mission Snapshot Egress "
_FIELDS = (
    "Scope",
    "IP",
    "City",
    "Country",
    "Latitude",
    "Longitude",
    "PoP ID",
    "Identity Source",
    "Matched CIDR",
    "Sample Time",
    "GeoIP Lookup Time",
    "Freshness",
    "Provider GeoIP IP",
    "Provider GeoIP City",
    "Provider GeoIP Country",
    "Provider GeoIP Latitude",
    "Provider GeoIP Longitude",
    "Provider GeoIP Freshness",
    "Provider GeoIP Source",
    "Discrepancy",
)
EGRESS_SNAPSHOT_COLUMNS = tuple(_PREFIX + field for field in _FIELDS)


def egress_identity(value: dict | None) -> dict | None:
    """Ignore polling times for invalidation; retain identity and confidence changes."""
    if value is None:
        return None
    result = {k: v for k, v in value.items() if k not in {"sampled_at", "lookup_at"}}
    if result.get("provider_geoip") is not None:
        result["provider_geoip"] = {
            k: v for k, v in result["provider_geoip"].items() if k != "lookup_at"
        }
    return result


def snapshot_egress_values(entry: GroundEntryPoint | None) -> dict:
    values = dict.fromkeys(_FIELDS, "")
    values["Scope"] = "Snapshot only; not leg-time history"
    if entry is not None:
        values.update(
            {
                "IP": entry.ip,
                "City": entry.city,
                "Country": entry.country,
                "Latitude": entry.latitude,
                "Longitude": entry.longitude,
                "PoP ID": entry.pop_id or "",
                "Identity Source": entry.identity_source,
                "Matched CIDR": entry.matched_cidr or "",
                "Sample Time": entry.sampled_at or "",
                "GeoIP Lookup Time": entry.lookup_at or "",
                "Freshness": entry.freshness,
                "Discrepancy": entry.discrepancy,
            }
        )
        if provider := entry.provider_geoip:
            values.update(
                {
                    "Provider GeoIP IP": provider.ip,
                    "Provider GeoIP City": provider.city,
                    "Provider GeoIP Country": provider.country,
                    "Provider GeoIP Latitude": provider.latitude,
                    "Provider GeoIP Longitude": provider.longitude,
                    "Provider GeoIP Freshness": provider.freshness,
                    "Provider GeoIP Source": provider.source,
                }
            )
    return {_PREFIX + key: value for key, value in values.items()}
