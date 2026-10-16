import type { StatusResponse } from '@/services/status';
import type { PopTransition } from '@/types/pop';

export const POP_NOTE =
  'PoP transitions may briefly interrupt calls (typically 1–2 seconds). Marked windows indicate possible transition timing.';
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
    summary,
    observation:
      observation?.status === 'known' && observation.entry
        ? `Observed PoP: ${[observation.entry.city, observation.entry.country].filter(Boolean).join(', ')}${observation.ip ? ` · ${observation.ip}` : ''}${observation.source === 'simulation' ? ' · simulated' : ''}`
        : 'Observed PoP unknown.',
    advisories: (status?.pop_advisories ?? []).map((advisory) => {
      const transition = forecast?.transitions.find(
        (item) => item.crossing.id === advisory.transition_id
      );
      const cities = transition ? ` ${popCities(transition)}.` : '';
      switch (advisory.kind) {
        case 'window':
          return `${POP_CAUTION}${cities}`;
        case 'overdue':
          return `Overdue PoP transition.${cities} Possible call interruption remains active until the destination is observed.`;
        case 'mismatch':
          return 'Observed PoP differs from the expected region. A transition is possible at any time; calls may be interrupted.';
        case 'observation_unknown':
          return 'Current PoP unknown; observed completion and stability cannot be confirmed.';
      }
    }),
  };
}
