import type { OverviewScenario } from '../fixtures/overview';

export function specialPoiPayload(
  scenario: OverviewScenario,
  category: string | null
): unknown | null {
  if (category === 'satellite') {
    return response(
      scenario.satellites.generatedAt ?? scenario.nowIso,
      scenario.satellites.items.map((item) =>
        dto(item.id, item.name, item.coordinate, 'satellite')
      )
    );
  }
  if (category === 'mission-event') {
    return response(
      scenario.missionEvents.generatedAt ?? scenario.nowIso,
      scenario.missionEvents.items.flatMap((item) =>
        item.coordinate
          ? [dto(item.id, item.label, item.coordinate, 'mission-event')]
          : []
      )
    );
  }
  return null;
}

function response(generatedAt: string | null, pois: readonly unknown[]) {
  return { pois, total: pois.length, timestamp: generatedAt };
}

function dto(
  id: string,
  name: string,
  coordinate: Readonly<{ latitude: number; longitude: number }>,
  category: string
) {
  return {
    poi_id: id,
    name,
    latitude: coordinate.latitude,
    longitude: coordinate.longitude,
    category,
    icon: category === 'satellite' ? 'satellite' : 'circle',
    active: true,
    eta_seconds: 60,
    eta_type: 'estimated',
    is_pre_departure: false,
    flight_phase: 'in_flight',
    distance_meters: 1,
    bearing_degrees: 0,
    course_status: 'on_course',
    is_on_active_route: true,
    projected_latitude: coordinate.latitude,
    projected_longitude: coordinate.longitude,
    projected_waypoint_index: 0,
    projected_route_progress: 0,
    route_aware_status: 'ahead_on_route',
  };
}
