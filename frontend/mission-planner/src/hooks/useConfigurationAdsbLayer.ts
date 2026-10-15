import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useOverviewAdsbSettings } from './api/useOverviewAdsbSettings';
import { overviewAdsbApi } from '@/services/overview-adsb';
import { projectAdsbCatalog } from '@/pages/adsb/overview-adsb-state';

export function useConfigurationAdsbLayer(active: boolean) {
  const client = useQueryClient();
  const settingsQuery = useOverviewAdsbSettings();
  const settings = settingsQuery.data;
  const enabled = active && settings?.enabled === true;
  const catalog = useQuery({
    queryKey: ['overview-adsb-catalog'],
    queryFn: ({ signal }) => overviewAdsbApi.getCatalog(signal),
    enabled,
    retry: false,
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: 'always',
  });
  const { refetch } = catalog;
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!enabled) {
      void client.cancelQueries({ queryKey: ['overview-adsb-catalog'] });
      return;
    }
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    const visible = () => {
      if (!document.hidden) {
        setNow(Date.now());
        void refetch();
      }
    };
    document.addEventListener('visibilitychange', visible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', visible);
    };
  }, [enabled, client, refetch]);
  useEffect(() => {
    if (
      settings &&
      catalog.data &&
      catalog.data.settings_revision > settings.revision
    )
      void client.invalidateQueries({ queryKey: ['overview-adsb-settings'] });
  }, [settings, catalog.data, client]);
  const contacts = useMemo(
    () =>
      settings
        ? projectAdsbCatalog(
            catalog.data?.contacts ?? [],
            settings,
            Math.max(now, catalog.dataUpdatedAt)
          )
        : [],
    [settings, catalog.data, catalog.dataUpdatedAt, now]
  );
  return {
    settings,
    contacts,
    contextContacts: contacts,
    settingsError: settingsQuery.isError,
    trafficError: catalog.isError,
    isLoading: enabled && catalog.isPending,
    sourceErrors: settings?.enabled
      ? (catalog.data?.sources.filter((source) => source.error) ?? [])
      : [],
  };
}
