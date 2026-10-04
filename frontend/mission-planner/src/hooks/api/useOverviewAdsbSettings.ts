import { useEffect } from 'react';
import { replaceEqualDeep, useQuery } from '@tanstack/react-query';
import { overviewAdsbApi, type AdsbSettings } from '@/services/overview-adsb';
export function useOverviewAdsbSettings() {
  const query = useQuery({
    queryKey: ['overview-adsb-settings'],
    queryFn: ({ signal }) => overviewAdsbApi.getSettings(signal),
    retry: false,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: 'always',
    structuralSharing: (oldData, newData) => {
      const old = oldData as AdsbSettings | undefined;
      const next = newData as AdsbSettings;
      return old && old.revision > next.revision
        ? old
        : replaceEqualDeep(oldData, newData);
    },
  });
  const { refetch } = query;
  useEffect(() => {
    const visible = () => {
      if (!document.hidden) void refetch();
    };
    document.addEventListener('visibilitychange', visible);
    return () => document.removeEventListener('visibilitychange', visible);
  }, [refetch]);
  return query;
}
