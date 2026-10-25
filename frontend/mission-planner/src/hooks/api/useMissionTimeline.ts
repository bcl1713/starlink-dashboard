import { useCallback, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { readMissionTimeline } from '@/services/missionTimeline';

class TimelineSourceChanged extends Error {}

export function useMissionTimeline(missionId: string, identity: string | null) {
  const client = useQueryClient();
  const [visible, setVisible] = useState(() => !document.hidden);
  const query = useQuery({
    queryKey: ['mission-timeline', missionId, identity],
    enabled: !!missionId && !!identity,
    queryFn: async ({ signal }) => {
      const snapshot = await readMissionTimeline(missionId, signal);
      const source = JSON.stringify([
        snapshot.store_id,
        snapshot.api_epoch,
        snapshot.source_mode,
        snapshot.simulation_run_id,
      ]);
      if (
        snapshot.schema_version !== 1 ||
        snapshot.mission_id !== missionId ||
        source !== identity
      ) {
        void client.invalidateQueries({ queryKey: ['operator-health'] });
        throw new TimelineSourceChanged(
          'Mission timeline source changed; waiting for current context'
        );
      }
      return { snapshot, receivedAt: performance.now() };
    },
    refetchInterval: visible ? 15000 : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
    networkMode: 'always',
  });
  const refresh = useCallback(() => {
    void client.invalidateQueries({
      queryKey: ['mission-timeline', missionId, identity],
    });
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
  return {
    snapshot:
      identity && !(query.error instanceof TimelineSourceChanged)
        ? query.data?.snapshot
        : undefined,
    receivedAt: query.data?.receivedAt ?? -Infinity,
    loading: !!identity && query.isPending,
    failed: query.isError,
    refreshing: query.isFetching,
    refresh,
  };
}
export type MissionTimelineState = ReturnType<typeof useMissionTimeline>;
