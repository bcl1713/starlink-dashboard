import {
  adaptPositionHistory,
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

interface HistoryRun {
  readonly hemisphere: 'west' | 'east';
  readonly points: readonly OverviewGeometryPoint[];
  readonly timestamps: readonly string[];
}

export interface HistoryIdRegistry {
  readonly reconcile: (
    runs: readonly HistoryRun[]
  ) => readonly OperationalFeature[];
}

export function createHistoryIdRegistry(): HistoryIdRegistry {
  let nextId = 1;
  let previous: { id: string; timestamps: readonly string[] }[] = [];
  return {
    reconcile(runs) {
      const used = new Set<string>();
      const features = runs.map((run) => {
        const candidates = previous
          .map((prior) => ({
            prior,
            overlap: prior.timestamps.filter((stamp) =>
              run.timestamps.includes(stamp)
            ),
          }))
          .filter(
            (candidate) =>
              candidate.overlap.length > 0 && !used.has(candidate.prior.id)
          )
          .sort(
            (left, right) =>
              right.overlap.length - left.overlap.length ||
              left.overlap[0].localeCompare(right.overlap[0]) ||
              left.prior.id.localeCompare(right.prior.id)
          );
        const id =
          candidates[0]?.prior.id ?? `history:${run.hemisphere}:${nextId++}`;
        used.add(id);
        return {
          id,
          layerId: `position-history-${run.hemisphere}` as VectorLayerId,
          kind: 'history-segment',
          label: `Position history ${run.hemisphere}`,
          geometry: { type: 'line', points: run.points },
          details: [{ label: 'Samples', value: String(run.points.length) }],
        } satisfies OperationalFeature;
      });
      previous = runs.map((run, index) => ({
        id: features[index].id,
        timestamps: run.timestamps,
      }));
      return features;
    },
  };
}

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
  const routeId = route?.route_id ?? 'none';
  return splitAtInternationalDateLine(route ? adaptRouteCoordinates(route) : [])
    .filter((points) => points.length > 1)
    .map((points, index) => ({
      id: `route:${direction}:${routeId}:${index}`,
      layerId: `planned-route-${direction}` as VectorLayerId,
      kind: 'route-segment',
      label: route?.route_name ?? `Planned route ${direction}`,
      geometry: { type: 'line', points },
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
          geometry: { type: 'line', points },
          details: [{ label: 'Satellite', value: split.link.satellite_id }],
        })) satisfies OperationalFeature[]
  );
}

function historyRuns(snapshot: OverviewDataSnapshot): readonly HistoryRun[] {
  const raw = snapshot.history.data
    ? splitAtInternationalDateLine(
        adaptPositionHistory(alignPositionHistory(snapshot.history.data))
      )
    : [];
  return raw.flatMap((segment) => {
    const runs: HistoryRun[] = [];
    let current: OverviewGeometryPoint[] = [];
    let hemisphere: 'west' | 'east' | null = null;
    const flush = () => {
      if (current.length > 1 && hemisphere) {
        runs.push({
          hemisphere,
          points: current,
          timestamps: current.flatMap((point) =>
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
