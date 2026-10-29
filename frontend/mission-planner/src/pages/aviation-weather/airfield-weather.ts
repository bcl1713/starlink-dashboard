import type { AviationCollection } from '@/services/aviation-features';
import type {
  AviationLayer,
  AviationSettings,
} from '@/services/aviation-weather';
import type { RoutePoint } from '@/services/routes';

export type Airfields = { departure?: RoutePoint; arrival?: RoutePoint };

export function routeAirfields(route?: {
  points?: RoutePoint[];
  waypoints?: (RoutePoint & { role?: string | null })[];
}): Airfields {
  if (!route?.points?.length) return {};
  return {
    departure:
      route.waypoints?.find((p) => p.role === 'departure') ?? route.points[0],
    arrival:
      route.waypoints?.find((p) => p.role === 'arrival') ?? route.points.at(-1),
  };
}

export function aviationLayerEnabled(
  settings: AviationSettings | undefined,
  layer: AviationLayer
): boolean {
  return !!(
    settings?.[layer] ||
    (layer !== 'sigmet' &&
      (settings?.departure_weather || settings?.arrival_weather))
  );
}

function distanceKm(a: RoutePoint, b: number[]): number {
  const rad = Math.PI / 180;
  const dlat = (b[1] - a.latitude) * rad;
  const dlon = (b[0] - a.longitude) * rad;
  const h =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(a.latitude * rad) * Math.cos(b[1] * rad) * Math.sin(dlon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(Math.min(1, h)));
}

export function airfieldCollection(
  data: AviationCollection,
  layer: AviationLayer,
  settings: AviationSettings,
  airfields: Airfields
): AviationCollection {
  if (layer === 'sigmet' || settings[layer]) return data;
  const selected = new Set<string>();
  for (const role of ['departure', 'arrival'] as const) {
    const point = airfields[role];
    if (!settings[`${role}_weather`] || !point) continue;
    let nearest: string | undefined;
    let distance = 10;
    for (const f of data.features) {
      if (f.geometry?.type !== 'Point') continue;
      const km = distanceKm(point, f.geometry.coordinates);
      if (km <= distance) {
        distance = km;
        nearest = f.id;
      }
    }
    if (nearest) selected.add(nearest);
  }
  return { ...data, features: data.features.filter((f) => selected.has(f.id)) };
}
