import {
  compareAwareTimestampInstants,
  compareAwareTimestampToEpochMilliseconds,
} from '../../services/monitoring-validation';
import type {
  GroundEntryPoint,
  MonitoringHistory,
  OverviewStatus,
  POIETAResponse,
} from '../../types/monitoring';
import type {
  OverviewActiveLinkData,
  OverviewRadarData,
  OverviewRouteData,
} from './overview-data-types';

const METRICS = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

export function safeNow(now: () => number): number | null {
  try {
    const value = now();
    return Number.isSafeInteger(value) ? value : null;
  } catch {
    return null;
  }
}

export function computeFreshnessForSource(
  source: string,
  timestamp: string | null,
  nowMs: number,
  cadenceSeconds: number
): { freshness: 'fresh' | 'stale' | 'unknown'; ageSeconds: number | null } {
  if (timestamp === null || !Number.isSafeInteger(nowMs)) {
    return { freshness: 'unknown' as const, ageSeconds: null };
  }
  const future = compareSourceTimestampToEpochMilliseconds(
    source,
    timestamp,
    nowMs,
    5
  );
  if (future === null || future > 0) {
    return { freshness: 'unknown' as const, ageSeconds: null };
  }
  const staleSeconds = Math.max(5, 3 * cadenceSeconds);
  const stale = compareSourceTimestampToEpochMilliseconds(
    source,
    timestamp,
    nowMs,
    -staleSeconds
  );
  const sameOrFutureNow = compareSourceTimestampToEpochMilliseconds(
    source,
    timestamp,
    nowMs
  );
  const ageSeconds =
    sameOrFutureNow !== null && sameOrFutureNow >= 0
      ? 0
      : computeWholeAgeSeconds(source, timestamp, nowMs);
  return {
    freshness: stale === null ? 'unknown' : stale < 0 ? 'stale' : 'fresh',
    ageSeconds,
  };
}

export function radarOutcome(frameTimestamp: string) {
  const sourceTimestamp = radarTimestampFromFrame(frameTimestamp);
  return sourceTimestamp === null
    ? {
        ok: false as const,
        error: {
          code: 'invalid-data' as const,
          message: 'Source data was invalid.' as const,
        },
      }
    : { ok: true as const, data: { frameTimestamp } };
}

export function sourceTimestamp(source: string, data: unknown): string | null {
  if (source === 'telemetry') return (data as OverviewStatus).timestamp;
  if (source === 'history') return historyTimestamp(data as MonitoringHistory);
  if (
    source === 'pois' ||
    source === 'satellites' ||
    source === 'missionEvents'
  ) {
    return (data as POIETAResponse).timestamp;
  }
  if (source === 'activeLink')
    return activeTimestamp(data as OverviewActiveLinkData);
  if (source === 'route') return routeTimestamp(data as OverviewRouteData);
  if (source === 'groundEntryPoint') {
    const gep = data as GroundEntryPoint;
    return gep.available ? gep.observed_at : null;
  }
  if (source === 'radar') {
    return radarTimestampFromFrame((data as OverviewRadarData).frameTimestamp)
      ? (data as OverviewRadarData).frameTimestamp
      : null;
  }
  return null;
}

export function semanticUnavailable(source: string, data: unknown): boolean {
  if (source === 'groundEntryPoint')
    return !(data as GroundEntryPoint).available;
  if (source !== 'route') return false;
  const route = data as OverviewRouteData;
  return (
    route.west.route_id === null &&
    route.east.route_id === null &&
    route.west.total === 0 &&
    route.east.total === 0
  );
}

export function radarTimestampFromFrame(frame: string): string | null {
  if (!/^(0|[1-9][0-9]*)$/.test(frame)) return null;
  const seconds = Number(frame);
  if (
    !Number.isSafeInteger(seconds) ||
    seconds < 946_684_800 ||
    seconds > 4_102_444_800
  )
    return null;
  return new Date(seconds * 1000).toISOString().replace('.000', '');
}

export function compareSourceTimestampToEpochMilliseconds(
  source: string,
  timestamp: string,
  epochMilliseconds: number,
  offsetSeconds?: number
): -1 | 0 | 1 | null {
  const comparable =
    source === 'radar' ? radarTimestampFromFrame(timestamp) : timestamp;
  return comparable === null
    ? null
    : compareAwareTimestampToEpochMilliseconds(
        comparable,
        epochMilliseconds,
        offsetSeconds
      );
}

function historyTimestamp(history: MonitoringHistory): string | null {
  let oldest: string | null = null;
  for (const metric of METRICS) {
    const series = history.series.find((item) => item.metric === metric);
    if (!series || series.samples.length === 0) return null;
    let latest = series.samples[0].timestamp;
    for (const sample of series.samples.slice(1)) {
      if (compareAwareTimestampInstants(sample.timestamp, latest) > 0)
        latest = sample.timestamp;
    }
    if (oldest === null || compareAwareTimestampInstants(latest, oldest) < 0)
      oldest = latest;
  }
  return oldest;
}

function activeTimestamp(data: OverviewActiveLinkData): string | null {
  const normal = data.normal.observed_at;
  const warning = data.warning.observed_at;
  if (normal === null || warning === null) return null;
  return compareAwareTimestampInstants(normal, warning) <= 0 ? normal : warning;
}

function routeTimestamp(data: OverviewRouteData): string | null {
  const west = data.west.revision_at;
  const east = data.east.revision_at;
  if (west === null || east === null) return null;
  return compareAwareTimestampInstants(west, east) <= 0 ? west : east;
}

function computeWholeAgeSeconds(
  source: string,
  timestamp: string,
  nowMs: number
): number | null {
  let low = 0;
  let high = Math.max(0, Math.ceil(Math.abs(nowMs) / 1000) + 31_622_400_000);
  while (low < high) {
    const middle = Math.floor((low + high + 1) / 2);
    const comparison = compareSourceTimestampToEpochMilliseconds(
      source,
      timestamp,
      nowMs,
      -middle
    );
    if (comparison === null) return null;
    if (comparison <= 0) low = middle;
    else high = middle - 1;
  }
  return low;
}
