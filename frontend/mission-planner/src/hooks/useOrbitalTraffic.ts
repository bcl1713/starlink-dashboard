import { useEffect, useState, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  overviewLinkSettingsApi,
  type OverviewLinkSettings,
} from '@/services/overview-link-settings';
import { OrbitalLifecycle } from '@/pages/orbital/lifecycle';
import type { OrbitalEndpoints } from '@/pages/orbital/types';

export function useOrbitalTraffic({
  settings,
  endpoints,
}: {
  settings: OverviewLinkSettings | undefined;
  endpoints: OrbitalEndpoints;
}) {
  const queryClient = useQueryClient();
  const [lifecycle] = useState(
    () =>
      new OrbitalLifecycle({
        refreshSettings: async () => {
          try {
            return await queryClient.fetchQuery({
              queryKey: ['overview-link-settings'],
              queryFn: ({ signal }) => overviewLinkSettingsApi.get(signal),
              staleTime: 0,
            });
          } catch {
            return queryClient.getQueryData<OverviewLinkSettings>([
              'overview-link-settings',
            ]);
          }
        },
      })
  );
  const state = useSyncExternalStore(
    lifecycle.subscribe,
    lifecycle.getState,
    lifecycle.getState
  );
  const enabled =
    settings?.orbital_traffic_enabled === true &&
    settings.starshield_link_enabled;
  useEffect(() => {
    lifecycle.mount();
    return () => lifecycle.dispose();
  }, [lifecycle]);
  useEffect(() => {
    lifecycle.setVisible(document.visibilityState !== 'hidden');
    lifecycle.update(settings, endpoints);
  }, [lifecycle, settings, endpoints]);
  useEffect(() => {
    if (!enabled) return;
    const changed = () =>
      lifecycle.setVisible(document.visibilityState !== 'hidden');
    document.addEventListener('visibilitychange', changed);
    return () => document.removeEventListener('visibilitychange', changed);
  }, [lifecycle, enabled]);
  useEffect(() => {
    if (state.status.kind !== 'off')
      queryClient.setQueryData(['orbital-runtime-status'], state.status);
  }, [queryClient, state.status]);
  return state;
}
