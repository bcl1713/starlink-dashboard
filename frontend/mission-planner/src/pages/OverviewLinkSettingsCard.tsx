import { Switch } from '@/components/ui/switch';
import { ConfigurationSection } from './ConfigurationSection';
import { useId } from 'react';
import { useOverviewLinkSettings } from '@/hooks/api/useOverviewLinkSettings';
import { useUpdateOverviewLinkSettings } from '@/hooks/api/useUpdateOverviewLinkSettings';

export function OverviewLinkSettingsCard() {
  const { data, isError } = useOverviewLinkSettings();
  const {
    mutate,
    isPending,
    isSuccess,
    isError: saveError,
  } = useUpdateOverviewLinkSettings();
  const id = useId();
  const controls = [
    {
      field: 'starshield_link_enabled',
      label: 'Starshield data link',
      description: 'Show aircraft-to-PoP traffic.',
    },
    {
      field: 'orbital_traffic_enabled',
      label: 'Orbital traffic view',
      description:
        'Show the experimental constellation and inferred traffic path.',
    },
    {
      field: 'x_band_link_enabled',
      label: 'X-band data link',
      description: 'Show the configured satellite link and its activity.',
    },
  ] as const;

  return (
    <ConfigurationSection
      title="Overview data links"
      label="Overview data link settings"
      description="Choose which traffic paths appear on Overview."
    >
      <div className="divide-y">
        {controls.map(({ field, label, description }) => (
          <div key={field} className="min-w-0 py-4 first:pt-0 last:pb-0">
            <label className="flex min-h-11 items-center justify-between gap-6 text-sm font-medium">
              <span>
                <span className="block">{label}</span>
                <span
                  id={`${id}-${field}`}
                  className="mt-1 block text-sm font-normal text-muted-foreground"
                >
                  {description}
                </span>
              </span>
              <Switch
                aria-label={label}
                checked={data?.[field] ?? false}
                disabled={!data || isPending}
                aria-describedby={`${id}-${field}`}
                onChange={(event) => mutate({ [field]: event.target.checked })}
              />
            </label>
          </div>
        ))}
      </div>
      {!data && !isError && <p role="status">Loading data link settings…</p>}
      {isError && <p role="alert">Data link settings unavailable</p>}
      {isPending && <p role="status">Saving data link settings…</p>}
      {isSuccess && <p role="status">Data link settings saved</p>}
      {saveError && (
        <p role="alert">Unable to save data link settings. Please try again.</p>
      )}
    </ConfigurationSection>
  );
}
