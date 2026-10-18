import { createClientId } from '@/lib/clientId';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  acknowledgeOperatorEvent,
  readEventSnapshot,
} from '@/services/operatorEvents';
import { operatorFailure } from '@/services/operator';
import type { AckRequest, OperationalEvent } from '@/types/operatorEvents';
interface PendingAcknowledgment {
  missionId: string;
  identity: string;
  epoch: string;
  key: string;
  body: AckRequest;
}
export function useOperatorEvents(missionId: string, identity: string | null) {
  const client = useQueryClient();
  const [visible, setVisible] = useState(() => !document.hidden);
  const [pending, setPending] = useState<PendingAcknowledgment | null>(null);
  const pendingRef = useRef<PendingAcknowledgment | null>(null);
  const [ackError, setAckError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState<string | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [lostPending, setLostPending] = useState(false);
  const inFlight = useRef(false);
  const scope = JSON.stringify([missionId, identity]);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const mounted = useRef(true);
  const pendingKey = `operator-event-pending:${missionId}`;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const query = useQuery({
    queryKey: ['operator-events', missionId, identity],
    enabled: !!missionId && !!identity,
    queryFn: async ({ signal }) => {
      const snapshot = await readEventSnapshot(missionId, signal);
      const sourceIdentity = JSON.stringify([
        snapshot.store_id,
        snapshot.api_epoch,
        snapshot.source_mode,
        snapshot.simulation_run_id,
      ]);
      if (snapshot.mission_id !== missionId || sourceIdentity !== identity) {
        void client.invalidateQueries({ queryKey: ['operator-health'] });
        throw new Error(
          'Operator event source changed; waiting for current store'
        );
      }
      return { snapshot, receivedAt: performance.now() };
    },
    refetchInterval: visible ? 15000 : 60000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    retry: false,
    networkMode: 'always',
  });
  const refresh = useCallback(() => {
    void client.invalidateQueries(
      { queryKey: ['operator-events', missionId, identity] },
      { cancelRefetch: false }
    );
  }, [client, missionId, identity]);
  useEffect(() => {
    function visibility() {
      setVisible(!document.hidden);
      if (!document.hidden) refresh();
    }
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('online', refresh);
    window.addEventListener('focus', refresh);
    return () => {
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('online', refresh);
      window.removeEventListener('focus', refresh);
    };
  }, [refresh]);
  useEffect(
    () =>
      client.getQueryCache().subscribe((event) => {
        if (
          event.type === 'updated' &&
          event.action.type === 'invalidate' &&
          ['operator-records', 'operator-brief'].includes(
            String(event.query.queryKey[0])
          )
        )
          refresh();
      }),
    [client, refresh]
  );
  useEffect(() => {
    pendingRef.current = null;
    setPending(null);
    setAckError(null);
    setLostPending(false);
    try {
      const value = sessionStorage.getItem(pendingKey);
      if (!value) return;
      const saved = JSON.parse(value) as PendingAcknowledgment;
      if (
        saved.missionId !== missionId ||
        typeof saved.identity !== 'string' ||
        typeof saved.epoch !== 'string' ||
        typeof saved.key !== 'string' ||
        saved.body?.schema_version !== 1 ||
        typeof saved.body.occurrence_id !== 'string' ||
        typeof saved.body.snapshot_token !== 'string' ||
        !Number.isInteger(saved.body.severity_generation)
      )
        throw new Error('Invalid pending acknowledgment');
      pendingRef.current = saved;
      setPending(saved);
    } catch {
      setLostPending(true);
      setStorageWarning(
        'Pending acknowledgment unavailable. Refresh saved state before acknowledging again.'
      );
    }
  }, [pendingKey, missionId]);
  function keep(value: PendingAcknowledgment | null) {
    pendingRef.current = value;
    setPending(value);
    try {
      if (value) sessionStorage.setItem(pendingKey, JSON.stringify(value));
      else sessionStorage.removeItem(pendingKey);
    } catch {
      setStorageWarning(
        'Acknowledgment retry is session-only. Keep this page open.'
      );
    }
  }
  async function send(request: PendingAcknowledgment) {
    if (
      inFlight.current ||
      request.identity !== identity ||
      request.missionId !== missionId
    )
      return;
    inFlight.current = true;
    setAcknowledging(true);
    setAckError(null);
    const requestScope = scope;
    try {
      await acknowledgeOperatorEvent(request.body, request.key, request.epoch);
      if (mounted.current && scopeRef.current === requestScope) {
        keep(null);
        refresh();
      }
    } catch (error) {
      if (mounted.current && scopeRef.current === requestScope) {
        const failure = operatorFailure(error);
        setAckError(
          failure.status === 409
            ? 'Event or source changed. Refresh, then dismiss this obsolete request before acknowledging the current occurrence.'
            : failure.status === 503
              ? 'Acknowledgment unavailable; source or storage could not be validated.'
              : 'Acknowledgment not confirmed. Retry the saved request.'
        );
      }
    } finally {
      inFlight.current = false;
      if (mounted.current) setAcknowledging(false);
    }
  }
  async function acknowledge(event: OperationalEvent) {
    if (
      lostPending ||
      !identity ||
      !query.data ||
      pendingRef.current ||
      !event.notification.generation ||
      !event.notification.acknowledgment_available ||
      !event.active ||
      event.notification.retired ||
      event.notification.acknowledged
    )
      return;
    const request: PendingAcknowledgment = {
      missionId,
      identity,
      epoch: query.data.snapshot.api_epoch,
      key: createClientId(),
      body: {
        schema_version: 1,
        occurrence_id: event.notification.generation,
        severity_generation: event.notification.severity_generation,
        snapshot_token: query.data.snapshot.snapshot_token,
      },
    };
    keep(request);
    await send(request);
  }
  return {
    snapshot: query.data?.snapshot,
    receivedAt: query.data?.receivedAt ?? -Infinity,
    failed: query.isError,
    loading: query.isPending,
    refreshing: query.isFetching,
    visible,
    refresh,
    acknowledge,
    acknowledging,
    pendingAcknowledgment: pending?.missionId === missionId ? pending : null,
    retryAcknowledgment: () =>
      pendingRef.current ? send(pendingRef.current) : Promise.resolve(),
    discardPending: () => {
      if (!inFlight.current) {
        keep(null);
        setLostPending(false);
        setAckError(null);
        refresh();
      }
    },
    acknowledgmentError: ackError,
    blocked:
      lostPending ||
      (!!pending &&
        pending.missionId === missionId &&
        pending.identity !== identity),
    storageWarning,
  };
}
export type OperatorEventsState = ReturnType<typeof useOperatorEvents>;
