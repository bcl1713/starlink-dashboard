"""Explicit generated vocabulary; legacy labels are adapted only for display."""

MISSION_POI_LABELS = {
    "departure": "Takeoff",
    "arrival": "Landing",
    "aar_start": "AR Begins",
    "aar_end": "AR Ends",
    "ka_coverage_exit": "KA Coverage Ends",
    "ka_coverage_entry": "KA Coverage Resumes",
    "ka_transition": "KA Satellite Handover",
    "ka_outage_start": "Planned KA Outage Begins",
    "ka_outage_end": "Planned KA Outage Ends",
    "x_band_transition": "X-Band Satellite Handover",
    "x_band_warning_start": "X-Band Restriction Begins",
    "x_band_warning_end": "X-Band Restriction Ends",
    "starshield_transition_start": "Starshield Transition Window Begins",
    "starshield_transition_end": "Starshield Transition Window Ends",
    "starshield_outage_start": "Planned Starshield Outage Begins",
    "starshield_outage_end": "Planned Starshield Outage Ends",
}

_LEGACY = {
    "aar_start": "AR\nStart",
    "aar_end": "AR\nEnd",
    "x_band_transition": "X-Band\nSwap",
    "x_band_warning_start": "X-Band Shut Down",
    "x_band_warning_end": "X-Band Turn On",
    "ka_coverage_exit": "CommKa\nExit",
    "ka_coverage_entry": "CommKa\nEnter",
    "ka_transition": "CommKa\nSwap",
    "ka_outage_start": "Ka\nLoss",
    "ka_outage_end": "Ka\nRestore",
    "starshield_outage_start": "Starshield\nLoss",
    "starshield_outage_end": "Starshield\nRestore",
    "starshield_transition_start": "Starshield transition entry",
    "starshield_transition_end": "Starshield transition exit",
}


def display_poi_name(poi):
    """Never rewrite storage, endpoint names, arbitrary edits or user-owned POIs."""
    if poi.generated_source != "mission-timeline":
        return poi.name
    if poi.kind in _LEGACY and poi.name == _LEGACY[poi.kind]:
        return MISSION_POI_LABELS[poi.kind]
    if poi.kind == "ka_transition" and poi.name.startswith("Ka Transition "):
        detail = poi.name.removeprefix("Ka Transition ")
        if " → " in detail:
            return MISSION_POI_LABELS[poi.kind] + " " + detail
    return poi.name
