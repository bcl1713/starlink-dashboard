import {
  computeFreshnessForSource,
  semanticUnavailable,
  sourceTimestamp,
} from './overview-freshness';
import type {
  OverviewDataSnapshot,
  OverviewManualResult,
  OverviewSlotData,
  OverviewSlotOutcome,
  OverviewSourceKey,
  OverviewSourceSlot,
} from './overview-data-types';
import { batchAnnouncement } from './overview-announcements';
import { SOURCE_ORDER, type OverviewHttpSlot } from './overview-sources';

type AnySlot = OverviewSourceSlot<unknown>;
export type SlotCommit = readonly [OverviewSourceKey, OverviewSlotOutcome];

export const emptyOverviewSnapshot = () =>
  projectSnapshot(
    Object.fromEntries(
      SOURCE_ORDER.map((key) => [key, emptySlot()])
    ) as SlotMap,
    'idle',
    null
  );

export type SlotMap = {
  -readonly [K in OverviewSourceKey]: OverviewDataSnapshot[K];
};

export function startSlots(
  snapshot: OverviewDataSnapshot,
  slots: readonly OverviewHttpSlot[],
  paused: boolean
) {
  const next = cloneSlots(snapshot);
  const writable = next as Record<string, AnySlot>;
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
) {
  const slots = cloneSlots(snapshot);
  const before = cloneSlots(snapshot);
  const writable = slots as Record<string, AnySlot>;
  for (const [slot, outcome] of outcomes) {
    const previous = slots[slot];
    if (!outcome.ok && outcome.error === null) {
      const timestamp =
        outcome.data === undefined
          ? previous.sourceTimestamp
          : sourceTimestamp(slot, outcome.data);
      const freshness =
        outcome.data === undefined || paused
          ? previous.freshness
          : computeFreshnessForSource(slot, timestamp, nowMs, cadenceSeconds)
              .freshness;
      writable[slot] = phaseSlot({
        ...(previous as AnySlot),
        data: outcome.data ?? previous.data,
        pending: outcome.pending ?? false,
        paused,
        freshness,
        sourceTimestamp: timestamp,
      });
      continue;
    }
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
            data: outcome.data ?? previous.data,
            pending: false,
            paused,
            error: outcome.error,
            sourceTimestamp:
              outcome.data === undefined
                ? previous.sourceTimestamp
                : sourceTimestamp(slot, outcome.data),
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

export function projectFreshness(
  snapshot: OverviewDataSnapshot,
  nowMs: number,
  cadenceSeconds: number,
  paused: boolean
) {
  const slots = cloneSlots(snapshot);
  const before = cloneSlots(snapshot);
  const writable = slots as Record<string, AnySlot>;
  for (const slot of Object.keys(slots) as OverviewSourceKey[]) {
    const current = slots[slot] as AnySlot;
    const freshness = paused
      ? current.freshness
      : computeFreshnessForSource(
          slot,
          current.sourceTimestamp,
          nowMs,
          cadenceSeconds
        ).freshness;
    writable[slot] = phaseSlot({ ...current, freshness, paused });
  }
  return projectSnapshot(
    slots,
    snapshot.manualResult,
    batchAnnouncement(snapshot, before, slots, snapshot.manualResult)
  );
}

export function projectPaused(snapshot: OverviewDataSnapshot, paused: boolean) {
  const slots = cloneSlots(snapshot);
  const writable = slots as Record<string, AnySlot>;
  for (const source of SOURCE_ORDER) {
    writable[source] = phaseSlot({ ...(slots[source] as AnySlot), paused });
  }
  return projectSnapshot(slots, snapshot.manualResult, snapshot.announcement);
}

export function setManualResult(
  snapshot: OverviewDataSnapshot,
  manualResult: OverviewManualResult
) {
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

export function withRadarDisabled(snapshot: OverviewDataSnapshot) {
  return projectRadar(snapshot, {
    availability: 'unavailable',
    pending: false,
    error: null,
  });
}

export const withRadarRetry = (
  snapshot: OverviewDataSnapshot,
  paused: boolean
) => projectRadar(snapshot, { pending: true, paused, error: null });

export const withRadarEnabled = (
  snapshot: OverviewDataSnapshot,
  availability: AnySlot['availability']
) => projectRadar(snapshot, { availability });

function projectRadar(snapshot: OverviewDataSnapshot, patch: Partial<AnySlot>) {
  const slots = cloneSlots(snapshot);
  slots.radar = phaseSlot({ ...slots.radar, ...patch }) as typeof slots.radar;
  return projectSnapshot(slots, snapshot.manualResult, snapshot.announcement);
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
  previous: AnySlot,
  data: OverviewSlotData,
  nowMs: number,
  cadenceSeconds: number,
  paused: boolean
) {
  const isUnavailable = semanticUnavailable(slot, data);
  const timestamp = sourceTimestamp(slot, data);
  const freshness = paused
    ? previous.freshness
    : computeFreshnessForSource(slot, timestamp, nowMs, cadenceSeconds)
        .freshness;
  return phaseSlot({
    ...previous,
    data,
    pending: false,
    paused,
    error: null,
    availability: isUnavailable ? 'unavailable' : 'available',
    freshness,
    sourceTimestamp: timestamp,
    transportLastAttemptAt: nowMs,
    transportLastSuccessAt: nowMs,
  });
}

export function phaseSlot<T>(
  slot: OverviewSourceSlot<T>
): OverviewSourceSlot<T> {
  let phase: OverviewSourceSlot<T>['phase'] = 'ready';
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
  return Object.fromEntries(
    SOURCE_ORDER.map((source) => [source, snapshot[source]])
  ) as SlotMap;
}
