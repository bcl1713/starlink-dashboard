import { classifyLatency, formatCoordinates } from './formatters';
import type {
  OverviewDataSnapshot,
  OverviewSourceSlot,
} from './overview-data-types';
import type { OverviewStatus } from '../../types/monitoring';

function telemetryState(slot: OverviewSourceSlot<OverviewStatus>): string {
  if (slot.paused || slot.phase === 'paused') {
    return `Telemetry paused - last updated ${
      slot.sourceTimestamp ?? 'unknown'
    }`;
  }
  if (
    (slot.pending || slot.phase === 'refreshing') &&
    slot.error &&
    slot.data
  ) {
    return 'Telemetry retained data after refresh failed';
  }
  if (slot.pending || slot.phase === 'initial-loading') {
    return slot.data
      ? 'Telemetry refreshing retained data'
      : 'Telemetry loading';
  }
  if (slot.error && slot.data) return 'Telemetry retained data after failure';
  if (slot.error) return 'Telemetry unavailable after refresh failed';
  if (slot.availability === 'unavailable' || !slot.data) {
    return 'Telemetry unavailable';
  }
  if (slot.freshness === 'stale' || slot.phase === 'stale') {
    return 'Telemetry stale';
  }
  return 'Telemetry fresh';
}

function routeState(snapshot: OverviewDataSnapshot): string {
  if (snapshot.route.pending && snapshot.route.error && snapshot.route.data) {
    return 'Route retained after refresh failed';
  }
  if (snapshot.route.error && !snapshot.route.data) return 'Route unavailable';
  const routes = [snapshot.route.data?.west, snapshot.route.data?.east].filter(
    (route) => route && route.total > 0
  );
  return routes[0]?.route_name
    ? `Active route ${routes[0].route_name}`
    : 'No active route';
}

function latencyState(status: OverviewStatus | undefined): string {
  const latency = status?.network.latency_ms ?? null;
  const threshold = classifyLatency(latency);
  if (threshold.state === 'unavailable') return 'Latency unavailable';
  if (threshold.state === 'critical') return 'Latency Critical at 200 ms';
  if (threshold.state === 'warning') return 'Latency Warning at 100 ms';
  return 'Latency normal below 100 ms';
}

function positionState(status: OverviewStatus | undefined): string {
  if (!status) return 'Position unavailable';
  const { latitude, longitude } = status.position;
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < -90 ||
    latitude > 90 ||
    longitude < -180 ||
    longitude > 180
  ) {
    return 'Position unavailable';
  }
  return `Position ${formatCoordinates(latitude, longitude)}`;
}

export function prioritySummary(snapshot: OverviewDataSnapshot): string {
  const status = snapshot.telemetry.data;
  return `${telemetryState(snapshot.telemetry)}. ${routeState(
    snapshot
  )}. ${positionState(status)}. ${latencyState(status)}.`;
}
