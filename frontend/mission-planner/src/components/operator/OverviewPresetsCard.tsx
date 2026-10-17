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
  overviewLinkSettingsApi,
  overviewPresetsApi,
  PRESET_NAMES,
  type OverviewPresetName,
  type OverviewLinkSettingsUpdate,
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
      settings,
      expected,
      version,
    }: {
      name: OverviewPresetName;
      action: 'save' | 'apply';
      settings: OverviewLinkSettingsUpdate;
      expected?: OverviewLinkSettingsUpdate;
      version: number;
    }) => {
      await client.cancelQueries({ queryKey: ['overview-link-settings'] });
      await client.cancelQueries({ queryKey: ['overview-presets'] });
      if (action === 'save') {
        const saved = await overviewPresetsApi.save(name, settings, version);
        await client.cancelQueries({ queryKey: ['overview-presets'] });
        client.setQueryData(
          ['overview-presets'],
          (current: typeof presets.data) =>
            current ? { ...current, [name]: saved } : current
        );
      } else {
        const saved = await overviewLinkSettingsApi.update(settings, expected);
        await client.cancelQueries({ queryKey: ['overview-link-settings'] });
        client.setQueryData(['overview-link-settings'], saved);
      }
      return `${labels[name]} preset ${action === 'save' ? 'saved' : 'applied'}`;
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ['overview-presets'] });
      void client.invalidateQueries({ queryKey: ['overview-link-settings'] });
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
      description="Save current visibility switches as a named bundle, then apply them to all Overview displays. Presets do not change weather providers, history windows or camera behavior."
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
                    settings: { ...visibility.data },
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
                const expected = Object.fromEntries(
                  Object.keys(preset.settings).map((field) => [
                    field,
                    visibility.data![field as keyof typeof visibility.data],
                  ])
                );
                mutation.mutate({
                  name,
                  action: 'apply',
                  settings: preset.settings,
                  expected,
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
