import type { OverviewPOIFilter } from '../../types/monitoring';
import {
  getActiveXLink,
  getGroundEntryPoint,
  getMissionEventETAs,
  getMonitoringHistory,
  getPOIETAs,
  getRouteCoordinates,
  getSatelliteETAs,
  getStatus,
} from '../../services/monitoring';
import type {
  OverviewActiveLinkData,
  OverviewDataSnapshot,
  OverviewDataServices,
  OverviewRouteData,
  UseOverviewDataOptions,
} from './overview-data-types';
import { HTTP_SLOTS, commitSlot } from './overview-data-reducer';
import type { OverviewHttpSlot, SlotOutcome } from './overview-data-reducer';
import {
  classifyOverviewError,
  computeSourceFreshness,
} from './overview-freshness';

export const DEFAULT_SERVICES: OverviewDataServices = {
  getStatus,
  getMonitoringHistory,
  getGroundEntryPoint,
  getPOIETAs,
  getSatelliteETAs,
  getMissionEventETAs,
  getRouteCoordinates,
  getActiveXLink,
};

const PERIODS = {
  telemetry: 1,
  pois: 1,
  satellites: 1,
  missionEvents: 1,
  activeLink: 1,
  route: 5,
  groundEntryPoint: 30,
  history: 10,
} as const satisfies Record<OverviewHttpSlot, number>;

export interface RequestRegistry {
  abortAll(): void;
  start(
    slot: OverviewHttpSlot,
    filter: OverviewPOIFilter
  ): Promise<SlotOutcome>;
}

type RequestRecord = {
  controller: AbortController;
  generation: number;
  promise: Promise<SlotOutcome>;
};

export function createOverviewRequestRegistry(
  services: OverviewDataServices
): RequestRegistry {
  const records = new Map<OverviewHttpSlot, RequestRecord>();
  const generations = new Map<OverviewHttpSlot, number>();

  const start = (slot: OverviewHttpSlot, filter: OverviewPOIFilter) => {
    const existing = records.get(slot);
    if (existing) return existing.promise;
    const controller = new AbortController();
    const generation = (generations.get(slot) ?? 0) + 1;
    generations.set(slot, generation);
    const promise = runSlot(services, slot, filter, controller.signal)
      .then(
        (data): SlotOutcome => ({ ok: true, data }),
        (error): SlotOutcome => ({
          ok: false,
          error: classifyOverviewError(error, controller.signal.aborted),
        })
      )
      .finally(() => {
        if (records.get(slot)?.generation === generation) records.delete(slot);
      });
    records.set(slot, { controller, generation, promise });
    return promise;
  };

  return {
    start,
    abortAll() {
      for (const record of records.values()) record.controller.abort();
      records.clear();
    },
  };
}

export function dueSlots(
  reason: 'scheduled' | 'manual' | 'bootstrap' | 'visibility',
  cadence: UseOverviewDataOptions['cadence'],
  anchors: Map<OverviewHttpSlot, number>,
  nowMs: number
): OverviewHttpSlot[] {
  if (reason === 'manual' || reason === 'bootstrap') return [...HTTP_SLOTS];
  if (cadence === 'paused') return [];
  return HTTP_SLOTS.filter((slot) => {
    const previous = anchors.get(slot);
    const period = Math.max(cadence, PERIODS[slot]) * 1000;
    return previous === undefined || Math.max(0, nowMs - previous) >= period;
  });
}

export function cadenceSeconds(
  cadence: UseOverviewDataOptions['cadence']
): number {
  return cadence === 'paused' ? 30 : cadence;
}

export function safeHidden(
  visibility: UseOverviewDataOptions['visibility']
): boolean {
  try {
    return visibility?.isHidden() ?? false;
  } catch {
    return false;
  }
}

export function defaultVisibility() {
  return {
    isHidden: () =>
      typeof document === 'undefined' ? false : document.hidden === true,
    subscribe(listener: () => void) {
      if (typeof document === 'undefined') return () => {};
      document.addEventListener('visibilitychange', listener);
      return () => document.removeEventListener('visibilitychange', listener);
    },
  };
}

export function refreshSnapshotFreshness(
  snapshot: OverviewDataSnapshot,
  nowMs: number,
  cadence: Exclude<UseOverviewDataOptions['cadence'], 'paused'>
): OverviewDataSnapshot {
  let next = snapshot;
  for (const slot of [
    'telemetry',
    'history',
    'pois',
    'activeLink',
    'route',
    'groundEntryPoint',
    'radar',
  ] as const) {
    const current = next[slot];
    if (!current.sourceTimestamp || current.availability === 'unavailable') {
      continue;
    }
    const freshness = computeSourceFreshness(
      current.sourceTimestamp,
      nowMs,
      cadence
    ).freshness;
    if (freshness !== current.freshness) {
      next = commitSlot(
        next,
        slot,
        { ok: true, data: current.data },
        current.transportLastSuccessAt ?? nowMs,
        cadence,
        false
      );
    }
  }
  return next;
}

async function runSlot(
  services: OverviewDataServices,
  slot: OverviewHttpSlot,
  filter: OverviewPOIFilter,
  signal: AbortSignal
) {
  if (slot === 'telemetry') return services.getStatus(signal);
  if (slot === 'pois') return services.getPOIETAs(filter, signal);
  if (slot === 'satellites') return services.getSatelliteETAs(signal);
  if (slot === 'missionEvents') return services.getMissionEventETAs(signal);
  if (slot === 'groundEntryPoint') return services.getGroundEntryPoint(signal);
  if (slot === 'history') {
    return services.getMonitoringHistory({
      rangeSeconds: 1800,
      stepSeconds: 1,
      signal,
    });
  }
  if (slot === 'activeLink') {
    const controller = signal as AbortSignal;
    const [normal, warning] = await Promise.all([
      services.getActiveXLink('normal', controller),
      services.getActiveXLink('warning', controller),
    ]);
    return { normal, warning } satisfies OverviewActiveLinkData;
  }
  const [west, east] = await Promise.all([
    services.getRouteCoordinates('west', signal),
    services.getRouteCoordinates('east', signal),
  ]);
  return { west, east } satisfies OverviewRouteData;
}
