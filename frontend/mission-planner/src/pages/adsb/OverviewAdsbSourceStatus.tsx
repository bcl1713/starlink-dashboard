import { useOverviewAdsbLayer } from '@/hooks/useOverviewAdsbLayer';
import { ConfigurationSection } from '../ConfigurationSection';
export function OverviewAdsbSourceStatus() {
  const { settings, sources, settingsError, trafficError } =
    useOverviewAdsbLayer();
  return (
    <ConfigurationSection
      title="ADS-B source status"
      description="Provider acquisition health and last successful observations."
    >
      {!settings && !settingsError && (
        <p role="status" className="text-sm">
          Loading ADS-B settings…
        </p>
      )}
      {settingsError && (
        <p role="alert" className="text-sm text-destructive">
          ADS-B settings unavailable
        </p>
      )}
      {settings && !settings.enabled && (
        <p className="text-sm text-muted-foreground">
          ADS-B aircraft layer disabled.
        </p>
      )}
      {settings?.enabled && sources.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No source status available.
        </p>
      )}
      {trafficError && (
        <p role="status" className="mb-3 text-sm text-amber-400">
          ADS-B traffic refresh unavailable.
        </p>
      )}
      <dl className="divide-y">
        {sources.map((source) => (
          <div
            key={source.key}
            className="grid gap-2 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]"
          >
            <dt className="break-words font-mono">{source.key}</dt>
            <dd className="min-w-0 space-y-1">
              <p
                className={source.error ? 'text-amber-400' : 'text-emerald-400'}
              >
                {source.error ?? 'Available'}
              </p>
              <p className="text-xs text-muted-foreground">
                Last success:{' '}
                {source.last_success_at_ms === null
                  ? 'Unavailable'
                  : new Date(source.last_success_at_ms).toLocaleString()}
              </p>
              {source.retry_at_ms !== null && (
                <p className="text-xs text-muted-foreground">
                  Retry after: {new Date(source.retry_at_ms).toLocaleString()}
                </p>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </ConfigurationSection>
  );
}
