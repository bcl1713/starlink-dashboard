import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getOperatorHealth,
  operatorFailure,
  readOperatingContext,
} from '@/services/operator';
import { readEventSnapshot } from '@/services/operatorEvents';
import {
  deriveOverviewAdvisories,
  overviewAdvisoryContext,
  snapshotMatchesOverviewContext,
} from '@/pages/overview-advisories';

/** Passive reader: no acknowledgment recovery, local alerts or operational commands. */
export function useOverviewAdvisories(missionNowMs: number) {
  const client = useQueryClient();
  const [visible, setVisible] = useState(() => !document.hidden);
  const [receiptClock, setReceiptClock] = useState(() => ({
    wall: Date.now(),
    monotonic: performance.now(),
  }));
  useEffect(() => {
    const timer = window.setInterval(
      () => setReceiptClock({ wall: Date.now(), monotonic: performance.now() }),
      1_000
    );
    return () => window.clearInterval(timer);
  }, []);
  const contextRead = useQuery({
    queryKey: ['operator-operating-context'],
    queryFn: readOperatingContext,
    refetchInterval: visible ? 5_000 : 60_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
    networkMode: 'always',
  });
  const health = useQuery({
    queryKey: ['operator-health'],
    queryFn: getOperatorHealth,
    refetchInterval: visible ? 15_000 : 60_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
    networkMode: 'always',
  });
  const budget = visible ? 45_000 : 150_000;
  const staleRead = (at: number) => !at || receiptClock.wall - at > budget;
  const context =
    contextRead.isError ||
    health.isError ||
    staleRead(contextRead.dataUpdatedAt) ||
    staleRead(health.dataUpdatedAt)
      ? null
      : overviewAdvisoryContext(contextRead.data, health.data);
  const scope = context ? JSON.stringify(context) : null;
  const query = useQuery({
    queryKey: ['overview-advisories', scope],
    enabled: !!context,
    queryFn: async ({ signal }) => {
      if (!context) throw new Error('Active advisory context unavailable');
      const snapshot = await readEventSnapshot(context.missionId, signal);
      if (!snapshotMatchesOverviewContext(snapshot, context))
        throw new Error('Advisory source changed; waiting for active context');
      // eslint-disable-next-line react-hooks/purity -- React Query invokes this async callback after the network read, outside render.
      return { snapshot, receivedAt: performance.now() };
    },
    refetchInterval: visible ? 15_000 : 60_000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: (failures, error) => {
      const failure = operatorFailure(error);
      return (
        failures === 0 &&
        failure.status === 409 &&
        failure.code === 'event_snapshot_changed' &&
        failure.retryable
      );
    },
    retryDelay: 100,
    networkMode: 'always',
  });
  useEffect(() => {
    const refresh = () => {
      for (const queryKey of [
        ['operator-operating-context'],
        ['operator-health'],
        ['overview-advisories'],
      ])
        void client.invalidateQueries({ queryKey }, { cancelRefetch: false });
    };
    const visibility = () => {
      setVisible(!document.hidden);
      if (!document.hidden) refresh();
    };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('online', refresh);
    };
  }, [client]);
  return deriveOverviewAdvisories({
    snapshot: query.data?.snapshot,
    context,
    missionNowMs,
    receivedAgeMs: Math.max(
      0,
      receiptClock.monotonic - (query.data?.receivedAt ?? -Infinity)
    ),
    visible,
    failed: query.isError || contextRead.isError || health.isError,
  });
}
