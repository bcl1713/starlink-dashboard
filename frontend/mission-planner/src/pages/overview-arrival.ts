import type {
  OverviewUpcomingPoi,
  OverviewUpcomingPoisResponse,
} from '@/services/overview-upcoming-pois';
import { isStatusStale, statusObservationAgeMs } from './status-freshness';

export interface ArrivalTiming {
  utc: string;
  timestamp: string;
  countdown: string;
  late: boolean;
  anticipated: boolean;
}
export interface ArrivalSection {
  label: string;
  name: string | null;
  timing: ArrivalTiming | null;
  unavailable: string;
}
export interface ArrivalPanelState {
  sections: ArrivalSection[];
  message: string | null;
  exception: string | null;
}

const CONTEXT_MESSAGES = {
  no_active_mission: 'No active mission leg.',
  route_unavailable: 'Active mission leg is not bound to the active route.',
  inconsistent_active_mission: 'Active mission state is inconsistent.',
} as const;

export function formatCountdown(ms: number, elapsed = false): string {
  if (ms <= 0) return '0 MIN';
  if (ms < 60_000) return '<1 MIN';
  const minutes = elapsed ? Math.floor(ms / 60_000) : Math.ceil(ms / 60_000);
  const hours = Math.floor(minutes / 60);
  return hours > 0
    ? `${hours} HR${minutes % 60 ? ` ${minutes % 60} MIN` : ''}`
    : `${minutes} MIN`;
}

function timing(
  timestamp: string | null,
  now: number,
  departure = false,
  anticipated = false
): ArrivalTiming | null {
  if (!timestamp) return null;
  const target = Date.parse(timestamp);
  if (!Number.isFinite(target)) return null;
  const iso = new Date(target).toISOString();
  const day = iso.slice(0, 10);
  const utc = `${day === new Date(now).toISOString().slice(0, 10) ? '' : `${day} `}${iso.slice(11, 16)}Z`;
  const late = departure && target < now;
  return {
    utc,
    timestamp: iso,
    countdown: late
      ? `${formatCountdown(now - target, true)} AGO`
      : formatCountdown(Math.max(0, target - now)),
    late,
    anticipated,
  };
}

function routeProgress(poi: OverviewUpcomingPoi): number | null {
  const progress = poi.projected_route_progress;
  return typeof progress === 'number' &&
    Number.isFinite(progress) &&
    progress >= 0 &&
    progress <= 100
    ? progress
    : null;
}

/** Derive both sections from the same endpoint snapshot and UTC clock. */
export function deriveArrivalPanel(
  response: OverviewUpcomingPoisResponse | undefined,
  now: number,
  refreshFailed = false
): ArrivalPanelState {
  const empty: ArrivalPanelState = {
    sections: [],
    message: null,
    exception: null,
  };
  if (!response)
    return { ...empty, message: 'Arrival information unavailable.' };
  const contextMessage =
    CONTEXT_MESSAGES[response.state as keyof typeof CONTEXT_MESSAGES];
  if (contextMessage) return { ...empty, message: contextMessage };
  const refreshUnavailable =
    refreshFailed || isStatusStale(response.calculated_at, now);
  const refreshException = refreshUnavailable
    ? 'Arrival refresh unavailable'
    : null;
  if (!response.flight_phase)
    return {
      ...empty,
      message: 'Flight phase unavailable.',
      exception: refreshException,
    };

  const departures = response.pois.filter((p) => p.kind === 'departure');
  const arrivals = response.pois.filter((p) => p.kind === 'arrival');
  const destination = arrivals.length === 1 ? arrivals[0] : null;
  if (response.flight_phase === 'pre_departure') {
    return {
      ...empty,
      exception: refreshException,
      sections: [
        {
          label: 'SCHEDULED DEPARTURE',
          name: departures.length === 1 ? departures[0].name : null,
          timing: refreshUnavailable
            ? null
            : timing(response.scheduled_departure_time, now, true),
          unavailable: 'Departure schedule unavailable',
        },
      ],
    };
  }
  if (response.flight_phase === 'post_arrival') {
    return {
      ...empty,
      exception: refreshException,
      sections: [
        {
          label: refreshUnavailable ? 'LANDING' : 'LANDED',
          name: destination?.name ?? null,
          timing: null,
          unavailable: refreshUnavailable
            ? 'Arrival state unavailable'
            : destination
              ? ''
              : 'Destination unavailable',
        },
      ],
    };
  }

  if (response.state === 'no_generated_pois')
    return {
      ...empty,
      message: 'No generated POIs.',
      exception: refreshException,
    };
  const positionAge =
    typeof response.position_observed_at === 'string'
      ? statusObservationAgeMs(response.position_observed_at, now)
      : null;
  const positionKnown =
    response.position_state !== 'unavailable' && positionAge !== null;
  const positionFresh =
    response.position_state === 'fresh' &&
    positionKnown &&
    positionAge! < 10_000;
  const exception =
    refreshException ??
    (!positionFresh
      ? positionKnown
        ? 'Position stale — ETA unavailable'
        : 'Position unavailable — ETA unavailable'
      : response.state === 'unavailable'
        ? 'ETA unavailable'
        : null);
  const allowTiming =
    !refreshUnavailable && positionFresh && response.state !== 'unavailable';
  const next = positionKnown
    ? response.pois
        .filter(
          (p) =>
            p.upcoming &&
            p.kind !== 'departure' &&
            routeProgress(p) !== null &&
            (p.kind !== 'arrival' || p.poi_id === destination?.poi_id)
        )
        .slice()
        .sort(
          (a, b) =>
            routeProgress(a)! - routeProgress(b)! ||
            a.poi_id.localeCompare(b.poi_id)
        )[0]
    : null;
  const section = (
    label: string,
    poi: OverviewUpcomingPoi | null
  ): ArrivalSection => ({
    label,
    name: poi?.name ?? null,
    timing:
      allowTiming && poi?.upcoming && poi.eta_type
        ? timing(
            poi.estimated_arrival_time,
            now,
            false,
            poi.eta_type === 'anticipated'
          )
        : null,
    unavailable: poi
      ? poi.upcoming
        ? 'ETA unavailable'
        : typeof response.current_route_progress === 'number' &&
            Number.isFinite(response.current_route_progress) &&
            routeProgress(poi) !== null &&
            response.current_route_progress >= routeProgress(poi)!
          ? 'Destination passed; awaiting landed state'
          : 'Arrival eligibility unavailable'
      : label === 'LANDING'
        ? 'Destination unavailable'
        : 'Next POI unavailable',
  });
  const sections = [];
  if (!next || next.poi_id !== destination?.poi_id)
    sections.push(section('NEXT POI', next ?? null));
  sections.push(section('LANDING', destination));
  return { ...empty, sections, exception };
}
