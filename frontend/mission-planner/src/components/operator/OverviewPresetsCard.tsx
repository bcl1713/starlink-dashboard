import {
  applyDisplayPreset,
  saveCurrentDisplayPreset,
} from '@/services/overview-preset-actions';
import {
  useMutation,
  useQuery,
  useQueryClient,
  useIsMutating,
} from '@tanstack/react-query';
import { ConfigurationSection } from '@/pages/ConfigurationSection';
import { Button } from '@/components/ui/button';
import { useOverviewLinkSettings } from '@/hooks/api/useOverviewLinkSettings';
import {
  overviewPresetsApi,
  PRESET_NAMES,
  type OverviewPresetName,
  type OverviewPreset,
} from '@/services/overview-link-settings';

const labels = {
  normal: 'Normal',
  communications: 'Communications',
  weather: 'Weather',
};
export function OverviewPresetsCard() {
  const client = useQueryClient();
  const visibility = useOverviewLinkSettings();
  const presets = useQuery({
    queryKey: ['overview-presets'],
    queryFn: ({ signal }) => overviewPresetsApi.get(signal),
    retry: false,
    refetchInterval: 5000,
  });
  const pending =
    useIsMutating({ mutationKey: ['overview-display-write'] }) > 0;
  const mutation = useMutation({
    mutationKey: ['overview-display-write'],
    networkMode: 'always',
    scope: { id: 'overview-link-settings' },
    retry: false,
    mutationFn: async ({
      name,
      action,
      preset,
      version,
    }: {
      name: OverviewPresetName;
      action: 'save' | 'apply';
      preset?: OverviewPreset;
      version: number;
    }) => {
      await client.cancelQueries({ queryKey: ['overview-link-settings'] });
      await client.cancelQueries({ queryKey: ['overview-presets'] });
      if (action === 'save') {
        const saved = await saveCurrentDisplayPreset(name, version);
        await client.cancelQueries({ queryKey: ['overview-presets'] });
        client.setQueryData(
          ['overview-presets'],
          (current: typeof presets.data) =>
            current ? { ...current, [name]: saved } : current
        );
      } else {
        if (!preset)
          throw new Error('Read the saved preset before applying it.');
        const result = await applyDisplayPreset(preset);
        if (result.legacy)
          return `${labels[name]} legacy preset applied to panels and map only. Weather was not saved in this preset; save the current view again to include weather.`;
      }
      return `${labels[name]} preset ${action === 'save' ? 'saved' : 'applied'}`;
    },
    onSettled: async () => {
      await Promise.all(
        [
          ['overview-presets'],
          ['overview-link-settings'],
          ['overview-weather-settings'],
          ['aviation-weather', 'settings'],
        ].map((queryKey) => client.invalidateQueries({ queryKey }))
      );
    },
  });
  const ready =
    !!visibility.data &&
    !visibility.isError &&
    !!presets.data &&
    !presets.isError &&
    !pending;
  return (
    <ConfigurationSection
      title="Display presets"
      description="Save panel, map and weather visibility for all Overview displays. Weather includes radar, METAR, TAF, SIGMET and route filtering, plus wind or temperature. Provider configuration, forecast level/horizon, acknowledgments, history windows and camera behavior are unchanged. Applying uses separate settings stores; any incomplete acknowledgment is reported for retry."
    >
      <div className="space-y-3">
        {PRESET_NAMES.map((name) => (
          <div key={name} className="flex flex-wrap items-center gap-2">
            <span className="w-full font-medium sm:w-40">
              {labels[name]}
              {presets.data?.[name]
                ? ` · saved v${presets.data[name].version}`
                : presets.data
                  ? ' · not saved'
                  : ''}
            </span>
            <Button
              variant="outline"
              disabled={!ready}
              onClick={() => {
                if (visibility.data)
                  mutation.mutate({
                    name,
                    action: 'save',
                    version: presets.data?.[name]?.version ?? 0,
                  });
              }}
            >
              Save current as {labels[name]}
            </Button>
            <Button
              disabled={!ready || !presets.data?.[name]}
              onClick={() => {
                const preset = presets.data?.[name];
                if (!preset || !visibility.data) return;
                mutation.mutate({
                  name,
                  action: 'apply',
                  preset,
                  version: preset.version,
                });
              }}
            >
              Apply {labels[name]}
            </Button>
          </div>
        ))}
      </div>
      {presets.isLoading && <p role="status">Loading saved presets…</p>}
      {presets.isError && (
        <p role="alert">
          Saved presets unavailable. Reconnect or refresh to retry.
        </p>
      )}
      {mutation.isPending && (
        <p role="status">Waiting for server acknowledgment…</p>
      )}
      {mutation.isSuccess && <p role="status">{mutation.data}</p>}
      {mutation.isError && (
        <p role="alert">
          Preset change not confirmed. {mutation.error.message} Review refreshed
          settings before retrying.
        </p>
      )}
    </ConfigurationSection>
  );
}
