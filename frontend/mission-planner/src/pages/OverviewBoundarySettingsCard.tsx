import { useId } from 'react';
import { Switch } from '@/components/ui/switch';
import { useOverviewLinkSettings } from '@/hooks/api/useOverviewLinkSettings';
import { useUpdateOverviewLinkSettings } from '@/hooks/api/useUpdateOverviewLinkSettings';
import { ConfigurationSection } from './ConfigurationSection';

export function OverviewBoundarySettingsCard() {
  const { data, isError } = useOverviewLinkSettings();
  const {
    mutate,
    isPending,
    isSuccess,
    isError: saveError,
  } = useUpdateOverviewLinkSettings();
  const id = useId();
  return (
    <ConfigurationSection
      title="Geographic boundaries"
      description="Optional globe layers, off by default. Saved for all Overview displays; no mission required."
    >
      <div className="divide-y">
        {(
          [
            [
              'country_borders_enabled',
              'Country borders',
              'Show international land borders and coastlines.',
            ],
            [
              'state_borders_enabled',
              'State/province borders',
              'Show worldwide first-order subdivisions where available.',
            ],
          ] as const
        ).map(([field, label, description]) => (
          <label
            key={field}
            className="flex min-h-11 items-center justify-between gap-6 py-4 text-sm font-medium first:pt-0"
          >
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
              aria-describedby={`${id}-${field}`}
              checked={data?.[field] ?? false}
              disabled={!data || isPending}
              onChange={(event) => mutate({ [field]: event.target.checked })}
            />
          </label>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Made with{' '}
        <a className="underline" href="https://www.naturalearthdata.com/">
          Natural Earth
        </a>
        . Geographic reference only. Dashed lines mark source-classified
        disputed or uncertain borders; coverage and boundaries may be incomplete
        or outdated.
      </p>
      {!data && !isError && <p role="status">Loading boundary settings…</p>}
      {isError && <p role="alert">Boundary settings unavailable</p>}
      {isPending && <p role="status">Saving boundary settings…</p>}
      {isSuccess && <p role="status">Boundary settings saved</p>}
      {saveError && (
        <p role="alert">Unable to save boundary settings. Please try again.</p>
      )}
    </ConfigurationSection>
  );
}
