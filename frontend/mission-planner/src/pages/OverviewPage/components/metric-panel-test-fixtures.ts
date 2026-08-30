import type { MonitoringHistory, POIETA } from '../../../types/monitoring';
import type { OverviewSourceSlot } from '../overview-data-types';

export const NOW = '2026-08-29T12:30:00Z';

export function history(
  series: MonitoringHistory['series']
): MonitoringHistory {
  return Object.freeze({
    generated_at: NOW,
    window_start: '2026-08-29T12:00:00Z',
    window_end: NOW,
    range_seconds: 1800,
    step_seconds: 60,
    series,
  });
}

export function samples(
  values: readonly (readonly [string, number | null])[]
): { timestamp: string; value: number | null }[] {
  return values.map(([timestamp, value]) => ({ timestamp, value }));
}

export function slot<T>(
  data: T | undefined,
  phase: OverviewSourceSlot<T>['phase'] = 'ready'
): OverviewSourceSlot<T> {
  return {
    data,
    phase,
    availability: data === undefined ? 'unknown' : 'available',
    freshness: phase === 'stale' ? 'stale' : 'fresh',
    sourceTimestamp: NOW,
    transportLastAttemptAt: 1,
    transportLastSuccessAt: 1,
    pending: phase === 'refreshing',
    paused: phase === 'paused',
    error:
      phase === 'error'
        ? { code: 'request-failed', message: 'Source refresh failed.' }
        : null,
  };
}

export function poi(
  overrides: Partial<POIETA> & Pick<POIETA, 'poi_id' | 'name' | 'eta_seconds'>
): POIETA {
  return {
    latitude: 1,
    longitude: 2,
    category: 'waypoint',
    icon: 'dot',
    active: true,
    eta_type: 'estimated',
    is_pre_departure: false,
    flight_phase: 'in_flight',
    distance_meters: 1000,
    bearing_degrees: 90,
    course_status: 'on_course',
    is_on_active_route: true,
    projected_latitude: 1,
    projected_longitude: 2,
    projected_waypoint_index: 1,
    projected_route_progress: 50,
    route_aware_status: 'ahead_on_route',
    ...overrides,
  };
}
