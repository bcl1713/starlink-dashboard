import { useStatus } from '@/hooks/api/useStatus';
import { useCurrentTime } from '@/hooks/useCurrentTime';
import type { StatusResponse } from '@/services/status';
import { projectPopAdvisories } from '@/pages/pop-advisory-projection';
import { isStatusStale } from '@/pages/status-freshness';

export function PopEvidenceView({
  status,
  failed = false,
}: {
  status?: StatusResponse;
  failed?: boolean;
}) {
  const view = projectPopAdvisories(status);
  const now = useCurrentTime(1_000);
  const observation = status?.pop_observation;
  const entry = observation?.entry;
  const provider = entry?.provider_geoip;
  return (
    <details className="ws-coverage" aria-label="PoP evidence">
      <summary>PoP evidence</summary>
      {(failed || (status && isStatusStale(status.timestamp, now))) && (
        <p role="status">
          Status stale or unavailable · last captured evidence.
        </p>
      )}
      <p>{view.observation}</p>
      <p className="ws-meta">
        IP sample:{' '}
        {observation?.sampled_at ?? entry?.sampled_at ?? 'unavailable'} · GeoIP
        lookup: {observation?.lookup_at ?? entry?.lookup_at ?? 'unavailable'}
      </p>
      {entry?.identity_source === 'operator_static_cidr' && (
        <p className="ws-meta">
          Catalog identity: {entry.pop_id} · operator-supplied static CIDR
          mapping {entry.matched_cidr}. Site coordinates are catalog city
          references; the mapping is not independently provider-verified.
        </p>
      )}
      {provider && (
        <p className="ws-meta">
          Provider GeoIP egress ({provider.source ?? 'provider unknown'}):{' '}
          {[provider.city, provider.country].filter(Boolean).join(', ')} ·{' '}
          {provider.latitude}°, {provider.longitude}° ·{' '}
          {provider.freshness ?? 'freshness unknown'} ·{' '}
          {provider.lookup_at ?? 'lookup time unavailable'}
        </p>
      )}
      {entry?.discrepancy && (
        <p>
          Provider GeoIP differs from the mapped PoP. Geographic error or remote
          backhaul remains possible; physical routing is unverified.
        </p>
      )}
      <p className="ws-meta">
        Forecast geography estimates the nearest PoP; it does not validate
        physical egress or service availability.
      </p>
      {view.advisories.map((advisory, index) => (
        <p key={index}>{advisory}</p>
      ))}
      {!!status?.pop_occurrences?.length && (
        <details>
          <summary>Forecast comparison</summary>
          <ul>
            {status.pop_occurrences.map((item) => (
              <li key={item.transition_id}>
                {item.from_city ?? 'PoP'} → {item.to_city ?? 'PoP'} ·{' '}
                {item.disposition}. Expected {item.expected_utc}; window{' '}
                {item.window_start_utc}–{item.window_end_utc}.
                {item.observed_at
                  ? ` First observed ${item.observed_at}; timing residual ${item.timing_residual_seconds}s.`
                  : ' Transition time unconfirmed.'}
              </li>
            ))}
          </ul>
        </details>
      )}
    </details>
  );
}

export function PopEvidence() {
  const status = useStatus();
  return <PopEvidenceView status={status.data} failed={status.isError} />;
}
