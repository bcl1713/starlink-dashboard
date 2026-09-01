import type { CDPSession, Page } from '@playwright/test';

import {
  appendBounded,
  EVIDENCE_LIMITS,
  retentionOutcome,
} from './overview-evidence-limits';
import type {
  CdpNetworkEvent,
  CdpNetworkRecord,
} from './overview-lifecycle-types';

interface CdpRequestEvent {
  readonly requestId: string;
  readonly timestamp: number;
  readonly frameId?: string;
  readonly loaderId?: string;
  readonly type?: string;
  readonly request: { readonly url: string; readonly method: string };
}
interface CdpResponseEvent {
  readonly requestId: string;
  readonly timestamp: number;
  readonly response: { readonly status: number };
}
interface CdpTerminalEvent {
  readonly requestId: string;
  readonly timestamp: number;
}

export async function startCdpNetworkCapture(
  page: Page,
  observe: (record: CdpNetworkRecord) => Promise<void>
) {
  const session = await page.context().newCDPSession(page);
  const records = new Map<string, CdpNetworkRecord>();
  const events: CdpNetworkEvent[] = [];
  const reports: Promise<void>[] = [];
  const overflowed = new Set<string>();
  let stopped: Promise<void> | undefined;
  const report = (record: CdpNetworkRecord) => {
    if (reports.length >= EVIDENCE_LIMITS.pendingReports) {
      overflowed.add('pendingReports');
      return;
    }
    const report = Promise.resolve().then(() => observe(record));
    reports.push(report);
    void report.catch(() => undefined);
  };
  const event = (value: CdpNetworkEvent) =>
    appendBounded(
      events,
      value,
      EVIDENCE_LIMITS.cdpEvents,
      'cdpEvents',
      overflowed
    );
  session.on('Network.requestWillBeSent', (value: CdpRequestEvent) => {
    const url = firstPartyApiPath(value.request.url);
    if (!url) return;
    if (
      !records.has(value.requestId) &&
      records.size >= EVIDENCE_LIMITS.cdpRecords
    ) {
      overflowed.add('cdpRecords');
      return;
    }
    const record: CdpNetworkRecord = {
      cdpRequestId: value.requestId,
      event: 'Network.requestWillBeSent',
      url,
      method: value.request.method,
      type: value.type ?? 'Other',
      requestTimestamp: value.timestamp,
      responseTimestamp: null,
      terminalTimestamp: null,
      terminalOutcome: 'pending',
      status: null,
      failureText: null,
      frameId: value.frameId ?? 'unknown-frame',
      loaderId: value.loaderId ?? 'unknown-loader',
      contextId: `${value.frameId ?? 'unknown-frame'}:${value.loaderId ?? 'unknown-loader'}`,
    };
    records.set(value.requestId, record);
    event({ ...record, name: record.event, timestamp: value.timestamp });
    report(record);
  });
  session.on('Network.responseReceived', (value: CdpResponseEvent) => {
    const record = records.get(value.requestId);
    if (!record) return;
    const next = {
      ...record,
      event: 'Network.responseReceived' as const,
      responseTimestamp: value.timestamp,
      status: value.response.status,
    };
    records.set(value.requestId, next);
    event({ ...next, name: next.event, timestamp: value.timestamp });
    report(next);
  });
  for (const [name, outcome] of [
    ['Network.loadingFinished', 'finished'],
    ['Network.loadingFailed', 'failed'],
  ] as const) {
    session.on(name, (value: CdpTerminalEvent) => {
      const record = records.get(value.requestId);
      if (!record) return;
      const next = {
        ...record,
        event: name,
        terminalTimestamp: value.timestamp,
        terminalOutcome: outcome,
        failureText: outcome === 'failed' ? 'network-failed' : null,
      } satisfies CdpNetworkRecord;
      records.set(value.requestId, next);
      event({ ...next, name: next.event, timestamp: value.timestamp });
      report(next);
    });
  }
  await session.send('Network.enable');
  return {
    records: () => [...records.values()],
    events: () => [...events],
    retention: () =>
      retentionOutcome(overflowed, {
        cdpEvents: events.length,
        cdpRecords: records.size,
        pendingReports: reports.length,
      }),
    stop: () => (stopped ??= stop(session, reports)),
  };
}

function firstPartyApiPath(rawUrl: string): string | null {
  try {
    const url = new URL(rawUrl);
    return url.pathname.startsWith('/api/') ? url.pathname : null;
  } catch {
    return null;
  }
}

async function stop(session: CDPSession, reports: readonly Promise<void>[]) {
  try {
    const settled = await Promise.allSettled(reports);
    const rejected = settled.find(
      (result): result is PromiseRejectedResult => result.status === 'rejected'
    );
    if (rejected) throw rejected.reason;
  } finally {
    (
      session as CDPSession & { removeAllListeners(): void }
    ).removeAllListeners();
    await session.detach();
  }
}
