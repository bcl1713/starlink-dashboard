import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { AdsbSettings, AdsbTrafficBundle } from '@/services/overview-adsb';
import { useOverviewAdsbSettings } from './api/useOverviewAdsbSettings';
import { useOverviewAdsbTraffic } from './api/useOverviewAdsbTraffic';
import {
  acceptAdsbBundle,
  emptyAdsbSnapshot,
  projectAdsbContacts,
} from '@/pages/adsb/overview-adsb-state';
export function useOverviewAdsbLayer() {
  const queryClient = useQueryClient();
  const settingsQuery = useOverviewAdsbSettings();
  const settings = settingsQuery.data;
  const trafficQuery = useOverviewAdsbTraffic(settings?.enabled === true);
  const bundle = trafficQuery.data;
  const [retained, setRetained] = useState(() => ({
    settings: undefined as AdsbSettings | undefined,
    bundle: undefined as AdsbTrafficBundle | undefined,
    snapshot: emptyAdsbSnapshot(),
  }));
  const snapshot = retained.snapshot;
  const [now, setNow] = useState(Date.now);
  const accepted = useMemo(
    () =>
      settings
        ? acceptAdsbBundle(snapshot, settings, bundle)
        : emptyAdsbSnapshot(),
    [snapshot, settings, bundle]
  );
  if (retained.settings !== settings || retained.bundle !== bundle) {
    setRetained({ settings, bundle, snapshot: accepted });
  }
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        const key = event.query.queryKey[0];
        if (
          event.type === 'updated' &&
          event.action.type === 'success' &&
          (key === 'overview-adsb-settings' || key === 'overview-adsb-traffic')
        ) {
          setNow(Date.now());
        }
      }),
    [queryClient]
  );
  useEffect(() => {
    if (settings && bundle && bundle.settings_revision > settings.revision)
      void queryClient.invalidateQueries({
        queryKey: ['overview-adsb-settings'],
      });
  }, [settings, bundle, queryClient]);
  useEffect(() => {
    if (!settings?.enabled) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    const visible = () => {
      if (!document.hidden) setNow(Date.now());
    };
    document.addEventListener('visibilitychange', visible);
    window.addEventListener('focus', visible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', visible);
      window.removeEventListener('focus', visible);
    };
  }, [settings?.enabled]);
  const contacts = useMemo(
    () =>
      settings ? projectAdsbContacts(accepted.contacts, settings, now) : [],
    [accepted.contacts, settings, now]
  );
  return {
    settings,
    contacts,
    sources: settings?.enabled ? accepted.sources : [],
    settingsError: settingsQuery.isError,
    trafficError: trafficQuery.isError,
  };
}
