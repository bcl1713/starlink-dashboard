"""Customer map cues at the route positions entering and leaving a PoP window."""

from app.mission.timeline_builder.event_pois import route_position
from app.services.poi_manager import POICreate
from app.mission.poi_display import MISSION_POI_LABELS


def transition_window_pois(mission, forecast, projector, parent_mission_id=None):
    if not mission.route_id or forecast is None or forecast.status != "ready":
        return ()
    result = []
    for transition in forecast.transitions:
        for edge, label, timestamp in (
            ("start", "entry", transition.window_start_utc),
            ("end", "exit", transition.window_end_utc),
        ):
            if not projector.start_time <= timestamp <= projector.end_time:
                continue
            latitude, longitude, segment = route_position(projector, timestamp)
            poi = POICreate(
                name=MISSION_POI_LABELS[f"starshield_transition_{edge}"],
                latitude=latitude,
                longitude=longitude,
                icon="satellite",
                category="mission-event",
                description="Boundary of the planned Starshield transition window.",
                route_id=mission.route_id,
                mission_id=parent_mission_id or mission.id,
                kind=f"starshield_transition_{edge}",
                expected_arrival_time=timestamp,
            )
            poi._route_segment_index = segment
            result.append(poi)
    return tuple(result)
