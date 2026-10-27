import { timeBlocks } from '@/components/timeline/time-blocks';
import type { StatusResponse } from '@/services/status';
import type { CallContinuityProjection, PopTransition } from '@/types/pop';

export const POP_NOTE =
  'PoP changes may drop calls and require reestablishment. RF may remain connected. Full windows are planned outages only without an alternative; coordinate X fallback when available.';
export const POP_CAUTION =
  'Starshield PoP transition possible — brief call interruption.';
export function popCities(transition: PopTransition) {
  const crossing = transition.crossing;
  return `${crossing.from_city || `PoP ${crossing.from_pop_id}`} → ${crossing.to_city || `PoP ${crossing.to_pop_id}`}`;
}
/** Present backend evidence without interpreting positions or changing service states. */
export function projectPopAdvisories(
  status: Partial<StatusResponse> | undefined
) {
  const forecast = status?.pop_forecast;
  const observation = status?.pop_observation;
  const summary = !forecast
    ? 'PoP forecast unavailable.'
    : forecast.status === 'ready'
      ? forecast.transitions.length
        ? `${forecast.transitions.length} predicted PoP transition${forecast.transitions.length === 1 ? '' : 's'}.`
        : 'No upcoming PoP transitions predicted.'
      : forecast.status === 'disabled'
        ? 'Starshield disabled.'
        : `PoP forecast ${forecast.status}${forecast.reason ? `: ${forecast.reason}` : '.'}`;
  return {
    ...presentCallContinuity(
      status?.call_continuity?.revision === forecast?.revision
        ? status?.call_continuity
        : null
    ),
    summary,
    observation:
      observation?.status === 'known' && observation.entry
        ? `${observation.source === 'simulation' ? 'Simulated PoP' : observation.entry.identity_source === 'operator_static_cidr' ? 'PoP (operator-supplied static CIDR mapping)' : 'Provider GeoIP egress (PoP identity unconfirmed)'}: ${[observation.entry.city, observation.entry.country].filter(Boolean).join(', ')}${observation.ip ? ` · ${observation.ip}` : ''} · ${observation.freshness ?? observation.entry.freshness ?? 'freshness unknown'}`
        : `PoP identity unavailable.${observation?.ip ? ` Public IP: ${observation.ip}.` : ''}`,
    advisories: (status?.pop_advisories ?? []).map((advisory) => {
      const transition = forecast?.transitions.find(
        (item) => item.crossing.id === advisory.transition_id
      );
      const cities = transition ? ` ${popCities(transition)}.` : '';
      switch (advisory.kind) {
        case 'window':
          return `${POP_CAUTION}${cities}`;
        case 'overdue':
          return `Forecast window passed without a confirmed destination.${cities} Actual transition time is unknown.`;
        case 'mismatch':
          return 'Egress evidence differs from the geographic forecast; remote backhaul or GeoIP error remains possible. This does not establish a current interruption.';
        case 'observation_unknown':
          return 'Current PoP evidence unavailable or stale; transition timing is unconfirmed.';
      }
    }),
  };
}

/** Display the shared classification; never infer capabilities from lane defaults. */
export function presentCallContinuity(
  projection?: CallContinuityProjection | null
) {
  const unresolved =
    !projection ||
    !projection.intervals.length ||
    projection.intervals.some((i) => i.classification === 'unknown');
  const transitionDetails: Record<
    string,
    { startUtc: string; endUtc: string; message: string }[]
  > = {};
  for (const interval of projection?.intervals ?? []) {
    const label = {
      planned_outage:
        'Planned communications outage — No secure-call transport.',
      existing_outage:
        'Existing communications outage — No secure-call transport.',
      x_fallback:
        'Planned X-Band fallback — coordinate before use; activation is not automatic.',
      advisory: `Transition advisory — alternative available: ${interval.usable_alternatives.join(', ')}.`,
      ordinary: 'No additional transition outage.',
      unknown:
        'Call continuity unresolved — alternative capability unavailable.',
    }[interval.classification];
    for (const id of interval.transition_ids) {
      const details = (transitionDetails[id] ??= []);
      details.push({
        startUtc: interval.start_utc,
        endUtc: interval.end_utc,
        message: label,
      });
    }
  }
  for (const id of Object.keys(transitionDetails)) {
    transitionDetails[id] = timeBlocks(
      transitionDetails[id],
      (detail) => detail.startUtc,
      (detail) => detail.endUtc,
      (detail) => detail.message,
      (detail, endUtc) => ({ ...detail, endUtc })
    );
  }
  return {
    continuity: unresolved
      ? 'Call continuity unresolved — complete planned outage totals unavailable.'
      : `Planned communications outage: ${projection!.planned_communications_outage_seconds}s · PoP contribution: ${projection!.pop_call_outage_seconds}s · Longest call outage: ${projection!.longest_call_outage_seconds}s.`,
    transitionDetails,
  };
}
