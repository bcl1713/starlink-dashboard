import type { MonitoringHistory, OverviewStatus } from '../../types/monitoring';
import { compareAwareTimestampInstants } from '../../services/monitoring-validation';
import { mergeTimestampedSamples } from './history';
import {
  computeSourceFreshness,
  semanticUnavailable,
  sourceTimestamp,
} from './overview-freshness';
import type {
  OverviewDataSnapshot,
  OverviewManualResult,
  OverviewSourceError,
  OverviewSourceKey,
  OverviewSourcePhase,
  OverviewSourceSlot,
} from './overview-data-types';
import { batchAnnouncement } from './overview-data-types';

export const HTTP_SLOTS = [
  'telemetry',
  'pois',
  'satellites',
  'missionEvents',
  'activeLink',
  'route',
  'groundEntryPoint',
  'history',
] as const;
export type OverviewHttpSlot = (typeof HTTP_SLOTS)[number];

export type OverviewSlotData = OverviewDataSnapshot[OverviewSourceKey]['data'];
export type SlotOutcome =
  | { ok: true; data: OverviewSlotData }
  | { ok: false; error: OverviewSourceError | null };
export type SlotCommit = readonly [OverviewSourceKey, SlotOutcome];

export function emptyOverviewSnapshot(): OverviewDataSnapshot {
  return projectSnapshot(
    Object.fromEntries(
      [...HTTP_SLOTS, 'radar'].map((key) => [key, emptySlot()])
    ) as SlotMap,
    'idle',
    null
  );
}

export type SlotMap = {
  -readonly [K in OverviewSourceKey]: OverviewDataSnapshot[K];
};

export function startSlots(
  snapshot: OverviewDataSnapshot,
  slots: readonly OverviewHttpSlot[],
  paused: boolean
): OverviewDataSnapshot {
  const next = cloneSlots(snapshot);
  const writable = next as Record<string, OverviewSourceSlot<unknown>>;
  for (const slot of slots)
    writable[slot] = { ...writable[slot], pending: true, paused };
  return projectSnapshot(next, snapshot.manualResult, snapshot.announcement);
}

export function commitSlots(
  snapshot: OverviewDataSnapshot,
  outcomes: readonly SlotCommit[],
  nowMs: number,
  cadenceSeconds: number,
  paused: boolean,
  manualResult?: OverviewManualResult
): OverviewDataSnapshot {
  const slots = cloneSlots(snapshot);
  const before = cloneSlots(snapshot);
  const writable = slots as Record<string, OverviewSourceSlot<unknown>>;
  for (const [slot, outcome] of outcomes) {
    const previous = slots[slot];
    if (!outcome.ok && outcome.error === null) continue;
    writable[slot] = phaseSlot(
      outcome.ok
        ? successSlot(
            slot,
            previous,
            outcome.data,
            nowMs,
            cadenceSeconds,
            paused
          )
        : {
            ...previous,
            pending: false,
            paused,
            error: outcome.error,
            transportLastAttemptAt: nowMs,
          }
    );
  }
  const result = manualResult ?? snapshot.manualResult;
  return projectSnapshot(
    slots,
    result,
    batchAnnouncement(snapshot, before, slots, result)
  );
}

export function setManualResult(
  snapshot: OverviewDataSnapshot,
  manualResult: OverviewManualResult
): OverviewDataSnapshot {
  const announcement =
    manualResult === 'success'
      ? 'Manual refresh complete.'
      : manualResult === 'partial'
        ? 'Manual refresh completed with partial failures.'
        : manualResult === 'failure'
          ? 'Manual refresh failed.'
          : snapshot.announcement;
  return projectSnapshot(
    cloneSlots(snapshot),
    manualResult,
    announcement === snapshot.announcement
      ? snapshot.announcement
      : announcement
  );
}

export function withRadarDisabled(
  snapshot: OverviewDataSnapshot
): OverviewDataSnapshot {
  const slots = cloneSlots(snapshot);
  slots.radar = phaseSlot({
    ...slots.radar,
    availability: 'unavailable',
    pending: false,
    error: null,
  });
  return projectSnapshot(slots, snapshot.manualResult, snapshot.announcement);
}

export function mergeTelemetryIntoHistory(
  history: MonitoringHistory | undefined,
  status: OverviewStatus | readonly OverviewStatus[],
  nowMs: number
): MonitoringHistory | undefined {
  if (!history) return undefined;
  const statuses = Array.isArray(status) ? status : [status];
  const samples = statuses.map(statusSamples);
  const mergeNow = latestTimestamp([
    history.window_end,
    ...history.series.flatMap((series) =>
      series.samples.map((item) => item.timestamp)
    ),
    ...statuses.map((item) => item.timestamp),
  ]);
  return {
    ...history,
    series: history.series.map((series) => ({
      ...series,
      samples: [
        ...mergeTimestampedSamples(
          series.samples,
          samples.flatMap((sample) => sample[series.metric] ?? []),
          mergeNow ?? new Date(nowMs).toISOString().replace('.000', '')
        ),
      ],
    })),
  };
}

function emptySlot<T>(): OverviewSourceSlot<T> {
  return {
    data: undefined,
    phase: 'initial-loading',
    availability: 'unknown',
    freshness: 'unknown',
    sourceTimestamp: null,
    transportLastAttemptAt: null,
    transportLastSuccessAt: null,
    pending: false,
    paused: false,
    error: null,
  };
}

function successSlot(
  slot: OverviewSourceKey,
  previous: OverviewSourceSlot<unknown>,
  data: OverviewSlotData,
  nowMs: number,
  cadenceSeconds: number,
  paused: boolean
): OverviewSourceSlot<unknown> {
  const unavailable = semanticUnavailable(slot, data);
  const timestamp = sourceTimestamp(slot, data);
  const freshness = paused
    ? previous.freshness
    : computeSourceFreshness(timestamp, nowMs, cadenceSeconds).freshness;
  return phaseSlot({
    ...previous,
    data,
    pending: false,
    paused,
    error: null,
    availability: unavailable ? 'unavailable' : 'available',
    freshness,
    sourceTimestamp: timestamp,
    transportLastAttemptAt: nowMs,
    transportLastSuccessAt: nowMs,
  });
}

export function phaseSlot<T>(
  slot: OverviewSourceSlot<T>
): OverviewSourceSlot<T> {
  let phase: OverviewSourcePhase = 'ready';
  if (slot.data === undefined && slot.pending) phase = 'initial-loading';
  else if (slot.error) phase = 'error';
  else if (slot.availability === 'unavailable') phase = 'unavailable';
  else if (slot.paused) phase = 'paused';
  else if (slot.freshness === 'stale') phase = 'stale';
  else if (slot.data !== undefined && slot.pending) phase = 'refreshing';
  return { ...slot, phase };
}

export function projectSnapshot(
  slots: SlotMap,
  manualResult: OverviewManualResult,
  announcement: string | null
): OverviewDataSnapshot {
  const required = [slots.telemetry, slots.history, slots.pois];
  const incomplete = required.some(
    (slot) => slot.data === undefined && slot.error === null
  );
  const totalFailure = required.every(
    (slot) => slot.data === undefined && slot.error !== null
  );
  const anyError = Object.values(slots).some((slot) => slot.error !== null);
  const initialState = incomplete
    ? 'initial-loading'
    : totalFailure
      ? 'total-error'
      : anyError
        ? 'partial-error'
        : 'ready';
  const successTimes = Object.values(slots)
    .map((slot) => slot.transportLastSuccessAt)
    .filter((value): value is number => value !== null);
  const globalTransportLastSuccessAt =
    successTimes.length === 0 ? null : Math.max(...successTimes);
  const readyAnnouncement =
    initialState === 'ready' && announcement === null
      ? 'Overview ready.'
      : initialState === 'total-error'
        ? 'Overview data failed to load.'
        : announcement;
  return {
    ...slots,
    initialState,
    manualResult,
    globalTransportLastSuccessAt,
    announcement: readyAnnouncement,
  };
}

export function cloneSlots(snapshot: OverviewDataSnapshot): SlotMap {
  return {
    telemetry: snapshot.telemetry,
    history: snapshot.history,
    activeLink: snapshot.activeLink,
    pois: snapshot.pois,
    satellites: snapshot.satellites,
    missionEvents: snapshot.missionEvents,
    route: snapshot.route,
    groundEntryPoint: snapshot.groundEntryPoint,
    radar: snapshot.radar,
  };
}

function statusSamples(status: OverviewStatus) {
  const timestamp = status.timestamp;
  return {
    latitude_degrees: { timestamp, value: status.position.latitude },
    longitude_degrees: { timestamp, value: status.position.longitude },
    latency_ms: { timestamp, value: status.network.latency_ms },
    throughput_down_mbps: {
      timestamp,
      value: status.network.throughput_down_mbps,
    },
    throughput_up_mbps: { timestamp, value: status.network.throughput_up_mbps },
    packet_loss_percent: {
      timestamp,
      value: status.network.packet_loss_percent,
    },
  };
}

function latestTimestamp(values: readonly string[]): string | null {
  return values.reduce<string | null>((latest, value) => {
    if (latest === null) return value;
    return compareAwareTimestampInstants(value, latest) > 0 ? value : latest;
  }, null);
}
