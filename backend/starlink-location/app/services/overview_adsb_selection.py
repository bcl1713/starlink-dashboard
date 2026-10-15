"""Installation-wide selection and observation-based contact lifetime."""

from collections.abc import Iterable
from typing import Literal

from app.models.overview_adsb import AdsbContact, AdsbSettings


def position_state(
    contact: AdsbContact, now_ms: float
) -> Literal["current", "stale", "expired"]:
    age = now_ms - contact.position_observed_at_ms
    if age < 0 or age >= 120000:
        return "expired"
    return "current" if age < 30000 else "stale"


def select_contacts(
    contacts: Iterable[AdsbContact], settings: AdsbSettings, now_ms: float
) -> list[AdsbContact]:
    if not settings.enabled:
        return []
    newest: dict[str, AdsbContact] = {}
    for contact in contacts:
        previous = newest.get(contact.hex)
        if previous is None or (
            contact.position_observed_at_ms,
            contact.acquired_at_ms,
        ) > (previous.position_observed_at_ms, previous.acquired_at_ms):
            newest[contact.hex] = contact
    included, excluded = set(settings.include_hexes), set(settings.exclude_hexes)
    selected = []
    for hex_code, contact in sorted(newest.items()):
        if hex_code in excluded or position_state(contact, now_ms) == "expired":
            continue
        if hex_code in included:
            selected.append(contact)
        elif settings.mode == "military_and_included" and contact.military is True:
            callsign = (contact.callsign or "").strip().upper()
            if not settings.callsign_substrings or any(
                part in callsign for part in settings.callsign_substrings
            ):
                selected.append(contact)
    return selected
