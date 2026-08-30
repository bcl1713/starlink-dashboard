import {
  compareAwareTimestampInstants,
  compareAwareTimestampToEpochMilliseconds,
} from '../../services/monitoring-validation';
import type { MonitoringHistory, OverviewStatus } from '../../types/monitoring';
import { mergeTimestampedSamples } from './history';
import type {
  OverviewSlotOutcome,
  OverviewSourceKey,
} from './overview-data-types';
import type { SlotCommit } from './overview-data-reducer';

export function acceptTelemetry(
  status: OverviewStatus,
  nowMs: number
): boolean {
  const comparison = compareAwareTimestampToEpochMilliseconds(
    status.timestamp,
    nowMs,
    5
  );
  return comparison !== null && comparison <= 0;
}

export function boundPendingTelemetry(
  statuses: readonly OverviewStatus[]
): OverviewStatus[] {
  const samples: { timestamp: string; value: OverviewStatus }[] = [];
  let newest: string | null = null;

  for (const status of statuses) {
    let timestamp: string;
    try {
      if (typeof status.timestamp !== 'string') continue;
      timestamp = status.timestamp;
    } catch {
      continue;
    }
    if (compareAwareTimestampToEpochMilliseconds(timestamp, 0) === null) {
      continue;
    }
    samples.push({ timestamp, value: status });
    if (
      newest === null ||
      compareAwareTimestampInstants(timestamp, newest) > 0
    ) {
      newest = timestamp;
    }
  }

  if (newest === null) return [];
  return mergeTimestampedSamples([], samples, newest).map(
    (sample) => sample.value
  );
}

export function historyContains(
  history: MonitoringHistory,
  timestamp: string
): boolean {
  return history.series.every((series) =>
    series.samples.some(
      (sample) =>
        compareAwareTimestampInstants(sample.timestamp, timestamp) === 0
    )
  );
}

export function buildSlotCommits(
  outcomes: readonly {
    slot: OverviewSourceKey;
    outcome: OverviewSlotOutcome;
  }[],
  historyData: MonitoringHistory | undefined,
  pendingTelemetry: readonly OverviewStatus[],
  nowMs: number
): { commits: SlotCommit[]; pending: OverviewStatus[] } {
  const commits: SlotCommit[] = [];
  const accepted: OverviewStatus[] = [];
  let serverHistory: MonitoringHistory | undefined;
  let historyOutcome: OverviewSlotOutcome | undefined;

  for (const { slot, outcome } of outcomes) {
    if (
      slot === 'telemetry' &&
      outcome.ok &&
      acceptTelemetry(outcome.data as OverviewStatus, nowMs)
    ) {
      accepted.push(outcome.data as OverviewStatus);
    }
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

export function mergeTelemetryBatch(
  retained: MonitoringHistory | undefined,
  server: MonitoringHistory | undefined,
  statuses: readonly OverviewStatus[],
  nowMs: number
): MonitoringHistory | undefined {
  const history = server ?? retained;
  if (!history) return undefined;

  const statusSamples = statuses.map(samplesFromStatus);
  const mergeNow = latestTimestamp([
    ...(retained ? historyTimestamps(retained) : []),
    ...(server ? [server.window_end, ...historyTimestamps(server)] : []),
    ...statuses.map((item) => item.timestamp),
  ]);

  return {
    ...history,
    series: history.series.map((series) => ({
      ...series,
      samples: [
        ...mergeTimestampedSamples(
          [
            ...(retained?.series.find((item) => item.metric === series.metric)
              ?.samples ?? []),
            ...statusSamples.flatMap((sample) => sample[series.metric] ?? []),
          ],
          server?.series.find((item) => item.metric === series.metric)
            ?.samples ?? [],
          mergeNow ?? new Date(nowMs).toISOString().replace('.000', '')
        ),
      ],
    })),
  };
}

function samplesFromStatus(status: OverviewStatus) {
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

function historyTimestamps(history: MonitoringHistory): string[] {
  return history.series.flatMap((series) =>
    series.samples.map((item) => item.timestamp)
  );
}
