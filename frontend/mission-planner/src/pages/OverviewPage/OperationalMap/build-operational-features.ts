import {
  adaptPositionHistory,
  adaptActiveLinkSegment,
  adaptRouteCoordinates,
  splitActiveLinkSegments,
  splitAtInternationalDateLine,
} from '../geometry';
import type { OverviewGeometryPoint } from '../geometry';
import { alignPositionHistory } from '../history';
import type { OverviewDataSnapshot } from '../overview-data-types';
import type { POIETA } from '../../../types/monitoring';
import { buildLayerStates } from './operational-layer-state';
import type {
  OperationalFeature,
  OperationalLayerState,
  VectorLayerId,
} from './operational-map-types';
import {
  createHistoryIdRegistry,
  type HistoryIdRegistry,
  type HistoryRun,
} from './history-id-registry';

export { createHistoryIdRegistry };

export function buildOperationalFeatures(
  snapshot: OverviewDataSnapshot,
  historyRegistry: HistoryIdRegistry
): {
  readonly features: readonly OperationalFeature[];
  readonly layerStates: readonly OperationalLayerState[];
} {
  const features: OperationalFeature[] = [];
  features.push(...routeFeatures('west', snapshot.route.data?.west));
  features.push(...routeFeatures('east', snapshot.route.data?.east));
  features.push(
    ...activeLinkFeatures('normal', snapshot.activeLink.data?.normal)
  );
  features.push(
    ...activeLinkFeatures('warning', snapshot.activeLink.data?.warning)
  );
  features.push(...historyRegistry.reconcile(historyRuns(snapshot)));
  features.push(
    ...poiFeatures('flight-route-markers', 'poi', snapshot.pois.data?.pois)
  );
  features.push(
    ...poiFeatures('satellites', 'satellite', snapshot.satellites.data?.pois)
  );
  features.push(
    ...poiFeatures(
      'mission-events',
      'mission-event',
      snapshot.missionEvents.data?.pois
    )
  );
  const gep = snapshot.groundEntryPoint.data;
  if (gep?.available && finiteLatLon(gep.latitude, gep.longitude)) {
    const latitude = Number(gep.latitude);
    const longitude = Number(gep.longitude);
    features.push({
      id: 'ground-entry-point',
      layerId: 'ground-entry-point-layer',
      kind: 'ground-entry-point',
      label: 'GEP',
      geometry: {
        type: 'point',
        latitude,
        longitude,
      },
      details: [{ label: 'Location', value: gep.display ?? 'GEP' }],
    });
  }
  const position = snapshot.telemetry.data?.position;
  if (position && finiteLatLon(position.latitude, position.longitude)) {
    features.push({
      id: 'current-position',
      layerId: 'current-position-layer',
      kind: 'current-position',
      label: 'Current position',
      geometry: {
        type: 'point',
        latitude: position.latitude,
        longitude: position.longitude,
      },
      details: [
        { label: 'Heading', value: String(normalizeHeading(position.heading)) },
      ],
    });
  }
  return {
    features,
    layerStates: buildLayerStates(snapshot, features),
  };
}

function routeFeatures(
  direction: 'west' | 'east',
  route = undefined as
    | NonNullable<OverviewDataSnapshot['route']['data']>['west']
    | undefined
) {
  const sourcePoints = route ? adaptRouteCoordinates(route) : [];
  const routeId = route?.route_id ?? 'none';
  return splitAtInternationalDateLine(sourcePoints)
    .filter((points) => points.length > 1)
    .map((points, index) => ({
      id: `route:${direction}:${routeId}:${index}`,
      layerId: `planned-route-${direction}` as VectorLayerId,
      kind: 'route-segment',
      label: route?.route_name ?? `Planned route ${direction}`,
      geometry: { type: 'line', points, sourcePoints },
      details: [{ label: 'Points', value: String(points.length) }],
    })) satisfies OperationalFeature[];
}

function activeLinkFeatures(
  state: 'normal' | 'warning',
  data:
    | NonNullable<OverviewDataSnapshot['activeLink']['data']>['normal']
    | undefined
) {
  return splitActiveLinkSegments(data?.links ?? []).flatMap(
    (split) =>
      split.segments
        .filter((points) => points.length > 1)
        .map((points, index) => ({
          id: `active-link:${state}:${split.link.satellite_id}:${index}`,
          layerId: `active-x-band-${state}` as VectorLayerId,
          kind: 'active-link',
          label: `Active X-band ${state}`,
          geometry: {
            type: 'line',
            points,
            sourcePoints: adaptActiveLinkSegment(split.link),
          },
          details: [{ label: 'Satellite', value: split.link.satellite_id }],
        })) satisfies OperationalFeature[]
  );
}

function historyRuns(snapshot: OverviewDataSnapshot): readonly HistoryRun[] {
  const source = snapshot.history.data
    ? adaptPositionHistory(alignPositionHistory(snapshot.history.data))
    : [];
  const realByTimestamp = new Map(
    source.flatMap((point) =>
      point.timestamp ? [[point.timestamp, point]] : []
    )
  );
  return splitAtInternationalDateLine(source).flatMap((segment) => {
    const runs: HistoryRun[] = [];
    let current: OverviewGeometryPoint[] = [];
    let hemisphere: 'west' | 'east' | null = null;
    const flush = () => {
      if (hemisphere) {
        const real = current.flatMap((point) => {
          const sourcePoint = point.timestamp
            ? realByTimestamp.get(point.timestamp)
            : undefined;
          return sourcePoint ?? point;
        });
        if (current.length < 2) {
          current = [];
          return;
        }
        runs.push({
          hemisphere,
          points: current,
          sourcePoints: real,
          timestamps: real.flatMap((point) =>
            point.timestamp ? [point.timestamp] : []
          ),
        });
      }
      current = [];
    };
    for (const point of segment) {
      const nextHemisphere = point.longitude < 0 ? 'west' : 'east';
      if (hemisphere !== null && hemisphere !== nextHemisphere) flush();
      hemisphere = nextHemisphere;
      current.push(point);
    }
    flush();
    return runs;
  });
}

function poiFeatures(
  layerId: VectorLayerId,
  kind: 'poi' | 'satellite' | 'mission-event',
  pois: readonly POIETA[] | undefined
): OperationalFeature[] {
  return (pois ?? [])
    .filter((poi) => finiteLatLon(poi.latitude, poi.longitude))
    .map((poi) => ({
      id: `${kind}:${poi.poi_id}`,
      layerId,
      kind,
      label: poi.name,
      geometry: {
        type: 'point',
        latitude: poi.latitude,
        longitude: poi.longitude,
      },
      details: [
        { label: 'Category', value: poi.category ?? kind },
        { label: 'ETA seconds', value: String(poi.eta_seconds) },
      ],
    }));
}

function finiteLatLon(
  latitude: unknown,
  longitude: unknown
): latitude is number {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    Number(latitude) >= -90 &&
    Number(latitude) <= 90 &&
    Number(longitude) >= -180 &&
    Number(longitude) <= 180
  );
}

export function normalizeHeading(value: number): number {
  return Number.isFinite(value) ? ((value % 360) + 360) % 360 : 0;
}
