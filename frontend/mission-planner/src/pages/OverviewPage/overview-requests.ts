import type {
  MonitoringHistory,
  OverviewPOIFilter,
  OverviewStatus,
} from '../../types/monitoring';
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
  OverviewDataServices,
  OverviewManualResult,
  OverviewSourceKey,
} from './overview-data-types';
import { mergeTelemetryBatch } from './overview-data-types';
import {
  type OverviewHttpSlot,
  type SlotCommit,
  type SlotOutcome,
} from './overview-data-reducer';
import {
  acceptTelemetry,
  boundPendingTelemetry,
  classifyOverviewError,
  historyContains,
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

type RequestRecord = {
  controller: AbortController;
  generation: number;
  promise: Promise<SlotOutcome>;
};
export function createOverviewRequestRegistry(services: OverviewDataServices) {
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
        (error): SlotOutcome => {
          const classified = classifyOverviewError(
            error,
            controller.signal.aborted
          );
          return {
            ok: false,
            error: classified,
            manualFailure: classified === null && !controller.signal.aborted,
          };
        }
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

export function manualResultFromOutcomes(
  outcomes: readonly { outcome: SlotOutcome }[]
): OverviewManualResult {
  let successes = 0;
  let failures = 0;
  for (const { outcome } of outcomes) {
    if (outcome.ok) successes += 1;
    else if (outcome.error || outcome.manualFailure) failures += 1;
  }
  if (successes + failures === 0) return 'idle';
  if (failures === 0) return 'success';
  return successes === 0 ? 'failure' : 'partial';
}

export function buildSlotCommits(
  outcomes: readonly { slot: OverviewSourceKey; outcome: SlotOutcome }[],
  historyData: MonitoringHistory | undefined,
  pendingTelemetry: readonly OverviewStatus[],
  nowMs: number
): { commits: SlotCommit[]; pending: OverviewStatus[] } {
  const commits: SlotCommit[] = [];
  const accepted: OverviewStatus[] = [];
  let serverHistory: MonitoringHistory | undefined;
  let historyOutcome: SlotOutcome | undefined;
  for (const { slot, outcome } of outcomes) {
    if (
      slot === 'telemetry' &&
      outcome.ok &&
      acceptTelemetry(outcome.data as OverviewStatus, nowMs)
    )
      accepted.push(outcome.data as OverviewStatus);
    if (slot === 'history' && outcome.ok) {
      serverHistory = outcome.data as MonitoringHistory;
      historyOutcome = outcome;
      continue;
    }
    if (slot === 'history') historyOutcome = outcome;
    commits.push([slot, outcome]);
  }
  const telemetry = [...pendingTelemetry, ...accepted];
  const history = mergeTelemetryBatch(
    historyData,
    serverHistory,
    telemetry,
    nowMs
  );
  if (!history) return { commits, pending: boundPendingTelemetry(telemetry) };
  const historyCommit: SlotCommit =
    historyOutcome?.ok === true
      ? ['history', { ok: true, data: history }]
      : historyOutcome === undefined
        ? ['history', { ok: false, error: null, data: history }]
        : ['history', { ...historyOutcome, data: history }];
  return {
    commits: [...commits.filter(([slot]) => slot !== 'history'), historyCommit],
    pending: telemetry.filter(
      (status) => !historyContains(history, status.timestamp)
    ),
  };
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
      () => services.getActiveXLink('normal', signal),
      () => services.getActiveXLink('warning', signal)
    );
    return { normal, warning };
  }
  const [west, east] = await settlePair(
    () => services.getRouteCoordinates('west', signal),
    () => services.getRouteCoordinates('east', signal)
  );
  return { west, east };
}

async function settlePair<T>(
  left: () => Promise<T>,
  right: () => Promise<T>
): Promise<[T, T]> {
  const [first, second] = await Promise.allSettled(
    [left, right].map(
      (supplier) => new Promise<T>((resolve) => resolve(supplier()))
    )
  );
  if (first.status === 'rejected') throw first.reason;
  if (second.status === 'rejected') throw second.reason;
  return [first.value, second.value];
}
