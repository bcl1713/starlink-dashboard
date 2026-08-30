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
  OverviewDataSnapshot,
  OverviewActiveLinkData,
  OverviewDataServices,
  OverviewManualResult,
  OverviewRouteData,
  OverviewSourceKey,
  OverviewSourceSlot,
  UseOverviewDataOptions,
} from './overview-data-types';
import { SOURCE_ORDER } from './overview-data-types';
import {
  cloneSlots,
  HTTP_SLOTS,
  phaseSlot,
  projectSnapshot,
} from './overview-data-reducer';
import type { OverviewHttpSlot, SlotOutcome } from './overview-data-reducer';
import { classifyOverviewError } from './overview-freshness';

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
    filter: OverviewPOIFilter,
    replace?: boolean
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
  const outcomes = new Map<OverviewHttpSlot, SlotOutcome>();

  const start = (
    slot: OverviewHttpSlot,
    filter: OverviewPOIFilter,
    replace = false
  ) => {
    const existing = records.get(slot);
    if (existing && !replace) return follow(slot, existing.generation);
    if (existing && replace) {
      existing.controller.abort();
      records.delete(slot);
    }
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
      .then((outcome) => {
        if ((generations.get(slot) ?? 0) === generation)
          outcomes.set(slot, outcome);
        return outcome;
      })
      .finally(() => {
        if (records.get(slot)?.generation === generation) records.delete(slot);
      });
    records.set(slot, { controller, generation, promise });
    return follow(slot, generation);
  };

  async function follow(slot: OverviewHttpSlot, generation: number) {
    let observed = generation;
    for (;;) {
      const record = records.get(slot);
      if (record && record.generation !== observed)
        observed = record.generation;
      const promise = records.get(slot)?.promise;
      const outcome = promise
        ? await promise
        : { ok: false as const, error: null };
      const latest = generations.get(slot) ?? 0;
      const replacement = records.get(slot);
      if (latest === observed) return outcome;
      if (!replacement) return outcomes.get(slot) ?? outcome;
      observed = replacement.generation;
    }
  }

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

export function manualResultFromOutcomes(
  outcomes: readonly { outcome: SlotOutcome }[]
): OverviewManualResult {
  let successes = 0;
  let failures = 0;
  for (const { outcome } of outcomes) {
    if (outcome.ok) successes += 1;
    else if (outcome.error) failures += 1;
  }
  return successes + failures === 0
    ? 'idle'
    : failures === 0
      ? 'success'
      : successes === 0
        ? 'failure'
        : 'partial';
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

export function projectPaused(
  snapshot: OverviewDataSnapshot,
  paused: boolean
): OverviewDataSnapshot {
  const slots = cloneSlots(snapshot);
  const writable = slots as Record<string, (typeof slots)[OverviewSourceKey]>;
  for (const source of SOURCE_ORDER) {
    writable[source] = phaseSlot<unknown>({
      ...(slots[source] as OverviewSourceSlot<unknown>),
      paused,
    }) as (typeof slots)[OverviewSourceKey];
  }
  return projectSnapshot(slots, snapshot.manualResult, snapshot.announcement);
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
    const [normal, warning] = await settlePair(
      services.getActiveXLink('normal', signal),
      services.getActiveXLink('warning', signal)
    );
    return { normal, warning } satisfies OverviewActiveLinkData;
  }
  const [west, east] = await settlePair(
    services.getRouteCoordinates('west', signal),
    services.getRouteCoordinates('east', signal)
  );
  return { west, east } satisfies OverviewRouteData;
}

async function settlePair<T>(
  left: Promise<T>,
  right: Promise<T>
): Promise<[T, T]> {
  const [first, second] = await Promise.allSettled([left, right]);
  if (first.status === 'rejected') throw first.reason;
  if (second.status === 'rejected') throw second.reason;
  return [first.value, second.value];
}
