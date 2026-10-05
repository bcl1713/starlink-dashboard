import { useOverviewAdsbLayer } from '@/hooks/useOverviewAdsbLayer';
import { useUpdateOverviewAdsbSettings } from '@/hooks/api/useUpdateOverviewAdsbSettings';
import { OverviewAdsbContactTable } from './OverviewAdsbContactTable';
import { OverviewAdsbLists } from './OverviewAdsbLists';
export function OverviewAdsbSettingsCard() {
  const { settings, contacts, sources, settingsError, trafficError } =
    useOverviewAdsbLayer();
  const { mutate, isPending, isSuccess, isError } =
    useUpdateOverviewAdsbSettings();
  const add = (field: 'include_hexes' | 'exclude_hexes', hex: string) => {
    if (settings) mutate({ [field]: [...new Set([...settings[field], hex])] });
  };
  return (
    <section
      aria-label="ADS-B aircraft settings"
      className="my-6 rounded-lg border p-4"
    >
      <h2 className="text-xl font-semibold">ADS-B aircraft</h2>
      <p className="text-sm text-muted-foreground">
        Shared across this installation. Configure worldwide traffic
        independently of the camera or mission.
      </p>
      <label className="mt-3 flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          role="switch"
          checked={settings?.enabled ?? false}
          disabled={!settings || isPending}
          onChange={(e) => mutate({ enabled: e.target.checked })}
        />
        ADS-B aircraft layer
      </label>
      <label className="mt-2 block">
        ADS-B mode
        <select
          className="ml-2 min-h-11 max-w-full rounded border bg-background p-2"
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
      {!settings && !settingsError && (
        <p role="status">Loading ADS-B settings…</p>
      )}
      {settingsError && <p role="alert">ADS-B settings unavailable</p>}
      {isPending && <p role="status">Saving ADS-B settings…</p>}
      {isSuccess && <p role="status">ADS-B settings saved</p>}
      {isError && (
        <p role="alert">Unable to save ADS-B settings. Please try again.</p>
      )}
      {trafficError && (
        <p role="status">
          Traffic refresh unavailable; retained positions expire at their
          original observation age.
        </p>
      )}
      {settings && (
        <>
          <OverviewAdsbContactTable
            contacts={contacts}
            disabled={isPending}
            onInclude={(hex) => add('include_hexes', hex)}
            onExclude={(hex) => add('exclude_hexes', hex)}
          />
          <OverviewAdsbLists
            settings={settings}
            disabled={isPending}
            onSave={(changes) => mutate(changes)}
          />
        </>
      )}
      {sources.length > 0 && (
        <section aria-label="ADS-B source status" className="mt-4">
          <h3 className="font-semibold">Source status</h3>
          <ul>
            {sources.map((source) => (
              <li key={source.key} className="break-words text-sm">
                <strong>{source.key}</strong>: {source.error ?? 'Available'} ·
                Last success:{' '}
                {source.last_success_at_ms === null
                  ? 'Unavailable'
                  : new Date(source.last_success_at_ms).toLocaleString()}
                {source.retry_at_ms !== null && (
                  <>
                    {' '}
                    · Retry after:{' '}
                    {new Date(source.retry_at_ms).toLocaleString()}
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="mt-4 text-sm">
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
    </section>
  );
}
