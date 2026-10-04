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
    <section
      className="my-6 rounded-lg border p-4"
      aria-label="Orbital traffic diagnostics"
    >
      <h2 className="text-xl font-semibold">Orbital traffic diagnostics</h2>
      <p>
        Public Starlink elements provide orbital context. They do not identify
        serving spacecraft.
      </p>
      <p>
        The experimental path uses inferred routing and an abstract PoP ground
        leg.
      </p>
      {isError && <p role="alert">Orbital diagnostics unavailable</p>}
      {!data && !isError && <p>Loading orbital diagnostics…</p>}
      {data && (
        <>
          <p>Status: {data.status}</p>
          <p>
            Eligible objects: {data.eligible_count ?? 0}. Rejected:{' '}
            {data.rejected_count ?? 0}. Truncated: {data.truncated_count ?? 0}.
          </p>
          <p>Catalog acquired: {data.acquired_at ?? 'Never'}</p>
          <p>Last provider attempt: {data.last_attempt_at ?? 'Never'}</p>
          <p>Retry after: {data.retry_after_at ?? 'No additional delay'}</p>
          <p>Arc fallback reason: {fallbackReason}</p>
          {data.provider_error && <p>{data.provider_error}</p>}
          {data.suspended && (
            <button
              type="button"
              disabled={resume.isPending}
              onClick={() => resume.mutate()}
            >
              Resume orbital provider
            </button>
          )}
        </>
      )}
      {resume.isPending && <p role="status">Resuming provider…</p>}
      {resume.isError && <p role="alert">Unable to resume provider</p>}
    </section>
  );
}
