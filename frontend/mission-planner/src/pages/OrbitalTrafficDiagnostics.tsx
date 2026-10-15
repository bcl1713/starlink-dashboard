import { Button } from '@/components/ui/button';
import { ConfigurationSection } from './ConfigurationSection';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { orbitalCatalogApi } from '@/services/orbital-catalog';
import type { OrbitalTrafficState } from './orbital/lifecycle';

export function OrbitalTrafficDiagnostics() {
  const client = useQueryClient();
  const { data, isError } = useQuery({
    queryKey: ['orbital-diagnostics'],
    queryFn: ({ signal }) => orbitalCatalogApi.status(signal),
    retry: false,
    refetchInterval: 60000,
    refetchIntervalInBackground: false,
  });
  const resume = useMutation({
    mutationFn: () => orbitalCatalogApi.resume(),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['orbital-diagnostics'] });
    },
  });
  const runtime = client.getQueryData<OrbitalTrafficState['status']>([
    'orbital-runtime-status',
  ]);
  const fallbackReason = runtime
    ? runtime.kind === 'ready' || runtime.reason === null
      ? 'None in last Overview observation'
      : (runtime.reason ?? runtime.kind)
    : (data?.fallback_reason ?? 'No Overview observation');
  return (
    <ConfigurationSection
      title="Orbital traffic diagnostics"
      description="Public Starlink elements provide orbital context, not serving spacecraft identity. The experimental path uses inferred routing and an abstract PoP ground leg."
    >
      {isError && <p role="alert">Orbital diagnostics unavailable</p>}
      {!data && !isError && <p role="status">Loading orbital diagnostics…</p>}
      {data && (
        <>
          <dl className="divide-y text-sm">
            {[
              ['Status', data.status],
              [
                'Catalog objects',
                `Eligible: ${data.eligible_count ?? 0} · Rejected: ${data.rejected_count ?? 0} · Truncated: ${data.truncated_count ?? 0}`,
              ],
              ['Catalog acquired', data.acquired_at ?? 'Never'],
              ['Last provider attempt', data.last_attempt_at ?? 'Never'],
              ['Retry after', data.retry_after_at ?? 'No additional delay'],
              ['Arc fallback reason', fallbackReason],
            ].map(([label, value]) => (
              <div
                key={label}
                className="grid gap-1 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]"
              >
                <dt className="font-medium text-muted-foreground">{label}</dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
          {data.provider_error && <p>{data.provider_error}</p>}
          {data.suspended && (
            <Button
              variant="outline"
              size="sm"
              type="button"
              disabled={resume.isPending}
              onClick={() => resume.mutate()}
            >
              Resume orbital provider
            </Button>
          )}
        </>
      )}
      {resume.isPending && <p role="status">Resuming provider…</p>}
      {resume.isError && <p role="alert">Unable to resume provider</p>}
    </ConfigurationSection>
  );
}
