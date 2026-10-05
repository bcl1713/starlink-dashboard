import { useConfigurationAdsbLayer } from '@/hooks/useConfigurationAdsbLayer';
import { Switch } from '@/components/ui/switch';
import { useUpdateOverviewAdsbSettings } from '@/hooks/api/useUpdateOverviewAdsbSettings';
import { OverviewAdsbContactTable } from './OverviewAdsbContactTable';
import { OverviewAdsbLists } from './OverviewAdsbLists';
import { ConfigurationSection } from '../ConfigurationSection';
export function OverviewAdsbSettingsCard({
  active = true,
}: {
  active?: boolean;
}) {
  const {
    settings,
    contacts,
    contextContacts,
    settingsError,
    trafficError,
    isLoading,
    sourceErrors,
  } = useConfigurationAdsbLayer(active);
  const { mutate, isPending, isSuccess, isError } =
    useUpdateOverviewAdsbSettings();
  const toggle = (field: 'include_hexes' | 'exclude_hexes', hex: string) => {
    if (!settings) return;
    const saved = settings[field];
    mutate({
      [field]: saved.includes(hex)
        ? saved.filter((value) => value !== hex)
        : [...saved, hex],
    });
  };
  return (
    <ConfigurationSection
      title="ADS-B aircraft"
      label="ADS-B aircraft settings"
      description="Shared across this installation. Select worldwide aircraft independently of the camera or mission."
    >
      <div className="space-y-5">
        <div className="grid items-center gap-4 md:grid-cols-2">
          <label className="flex min-h-11 items-center justify-between gap-4 text-sm font-medium md:pr-8">
            <span>ADS-B aircraft layer</span>
            <Switch
              aria-label="ADS-B aircraft layer"
              checked={settings?.enabled ?? false}
              disabled={!settings || isPending}
              onChange={(e) => mutate({ enabled: e.target.checked })}
            />
          </label>
          <label className="flex min-h-11 flex-wrap items-center justify-between gap-3 text-sm font-medium">
            ADS-B mode
            <select
              className="min-h-11 max-w-full rounded-md border bg-background px-3 font-normal"
              aria-label="ADS-B mode"
              value={settings?.mode ?? 'military_and_included'}
              disabled={!settings || isPending}
              onChange={(e) =>
                mutate({
                  mode:
                    e.target.value === 'included_only'
                      ? 'included_only'
                      : 'military_and_included',
                })
              }
            >
              <option value="military_and_included">Military + included</option>
              <option value="included_only">Included only</option>
            </select>
          </label>
        </div>
        <div className="text-sm empty:hidden" aria-live="polite">
          {!settings && !settingsError && (
            <p role="status">Loading ADS-B settings…</p>
          )}
          {settingsError && (
            <p role="alert" className="text-destructive">
              ADS-B settings unavailable
            </p>
          )}
          {isPending && <p role="status">Saving ADS-B settings…</p>}
          {isSuccess && (
            <p role="status" className="text-emerald-400">
              ADS-B settings saved
            </p>
          )}
          {isError && (
            <p role="alert" className="text-destructive">
              Unable to save ADS-B settings. Please try again.
            </p>
          )}
          {trafficError && (
            <p role="status" className="text-amber-400">
              Traffic refresh unavailable; retained positions expire at their
              original observation age.
            </p>
          )}
        </div>
        {isLoading && (
          <p role="status" className="text-sm text-muted-foreground">
            Loading aircraft catalog…
          </p>
        )}
        {sourceErrors?.map((source) => (
          <p key={source.key} role="status" className="text-sm text-amber-400">
            {source.key === 'military'
              ? 'Military source'
              : `Aircraft ${source.key.slice(4)}`}
            : {source.error}.
            {source.retry_at_ms !== null &&
              ` Next retry ${new Date(source.retry_at_ms).toLocaleTimeString()}.`}
          </p>
        ))}
        {settings && (
          <>
            <OverviewAdsbContactTable
              contacts={contacts}
              disabled={isPending}
              onInclude={(hex) => toggle('include_hexes', hex)}
              onExclude={(hex) => toggle('exclude_hexes', hex)}
            />
            <OverviewAdsbLists
              settings={settings}
              contacts={contextContacts}
              disabled={isPending}
              onSave={(changes) => mutate(changes)}
            />
          </>
        )}
        <p className="text-xs text-muted-foreground">
          Aircraft data:{' '}
          <a
            className="underline"
            href="https://www.adsb.lol/"
            target="_blank"
            rel="noreferrer"
          >
            adsb.lol
          </a>{' '}
          ·{' '}
          <a
            className="underline"
            href="https://opendatacommons.org/licenses/odbl/1-0/"
            target="_blank"
            rel="noreferrer"
          >
            ODbL license
          </a>
        </p>
      </div>
    </ConfigurationSection>
  );
}
