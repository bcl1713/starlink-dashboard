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
      field: 'x_band_link_enabled',
      label: 'X-band data link',
      description: 'Show the configured satellite link and its activity.',
    },
  ] as const;

  return (
    <section
      className="my-6 rounded-lg border p-4"
      aria-label="Overview data link settings"
    >
      <h2 className="text-xl font-semibold">Overview data links</h2>
      <div className="mt-3 space-y-3">
        {controls.map(({ field, label, description }) => (
          <div key={field}>
            <label className="flex min-h-11 items-center gap-3">
              <input
                type="checkbox"
                role="switch"
                checked={data?.[field] ?? false}
                disabled={!data || isPending}
                aria-describedby={`${id}-${field}`}
                onChange={(event) => mutate({ [field]: event.target.checked })}
              />
              {label}
            </label>
            <p id={`${id}-${field}`} className="text-sm text-muted-foreground">
              {description}
            </p>
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
    </section>
  );
}
