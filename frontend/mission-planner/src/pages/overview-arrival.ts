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
  key:
    | 'destination'
    | 'scheduled_departure'
    | 'movement'
    | 'next_event'
    | 'landing';
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
  const utc = `${day === new Date(now).toISOString().slice(0, 10) ? '' : `${day} `}${iso.slice(11, 16)} Zulu`;
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
  refreshFailed = false,
  missionNowMs = now,
  flightEventsOnly = false
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
  if (response.source === 'manual') {
    const destination = response.pois.find((p) => p.kind === 'arrival');
    const fresh = (timestamp: string | null | undefined) => {
      const age = timestamp ? statusObservationAgeMs(timestamp, now) : null;
      return age !== null && age < 10_000;
    };
    const usable =
      !refreshUnavailable &&
      response.state === 'available' &&
      response.position_state === 'fresh' &&
      fresh(response.position_observed_at) &&
      fresh(response.speed_observed_at);
    return {
      ...empty,
      exception: refreshException,
      sections: [
        {
          key: 'destination',
          label: 'Destination',
          name: destination?.name ?? null,
          timing:
            usable && destination
              ? timing(destination.estimated_arrival_time, now)
              : null,
          unavailable: destination
            ? 'ETA unavailable'
            : 'Destination unavailable',
        },
      ],
    };
  }
  if (!response.flight_phase)
    return {
      ...empty,
      message: 'Flight phase unavailable.',
      exception: refreshException,
    };

  const movement = response.movement_state;
  const movementAge = response.movement_observed_at
    ? statusObservationAgeMs(response.movement_observed_at, now)
    : null;
  const movementFresh = movementAge !== null && movementAge < 10_000;
  const groundLabels: Record<string, string> = {
    taxi_out: 'Taxi Out',
    probable_landed_rollout: 'Landed · Inferred',
    taxi_in: 'Taxi In',
    parked_at_stop: 'Parked · Intermediate Stop',
    parked: 'Parked',
  };
  if (
    movement &&
    groundLabels[movement] &&
    (movement !== 'parked' || response.on_blocks_at)
  ) {
    const uncertain =
      response.movement_uncertain || !movementFresh || refreshUnavailable;
    return {
      ...empty,
      exception: uncertain ? 'Movement state uncertain or stale' : null,
      sections: [
        {
          key: 'movement',
          label: groundLabels[movement],
          name: null,
          timing: null,
          unavailable: uncertain
            ? 'Last recorded state; confirmation unavailable'
            : '',
        },
      ],
    };
  }
  const departures = response.pois.filter((p) => p.kind === 'departure');
  const arrivals = response.pois.filter((p) => p.kind === 'arrival');
  const destination = arrivals.length === 1 ? arrivals[0] : null;
  if (response.flight_phase === 'pre_departure') {
    return {
      ...empty,
      exception: refreshException,
      sections: [
        {
          key: 'scheduled_departure',
          label: 'Scheduled Departure',
          name: departures.length === 1 ? departures[0].name : null,
          timing: refreshUnavailable
            ? null
            : timing(response.scheduled_departure_time, missionNowMs, true),
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
          key: 'landing',
          label: refreshUnavailable ? 'Landing' : 'Landed',
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
            (!flightEventsOnly ||
              p.kind === 'arrival' ||
              p.kind === 'aar_start' ||
              p.kind === 'aar_end') &&
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
    key: 'next_event' | 'landing',
    label: string,
    poi: OverviewUpcomingPoi | null
  ): ArrivalSection => ({
    key,
    label,
    name: poi?.name ?? null,
    timing:
      allowTiming && poi?.upcoming && poi.eta_type
        ? timing(
            poi.estimated_arrival_time,
            missionNowMs,
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
          : routeProgress(poi) === null
            ? 'Destination route position unavailable'
            : 'Route position unavailable — ETA unavailable'
      : key === 'landing'
        ? 'Destination unavailable'
        : flightEventsOnly
          ? 'Next flight event unavailable'
          : 'Next POI unavailable',
  });
  const sections = [];
  if (!next || next.poi_id !== destination?.poi_id)
    sections.push(
      section(
        'next_event',
        flightEventsOnly ? 'Next Flight Event' : 'Next POI',
        next ?? null
      )
    );
  sections.push(section('landing', 'Landing', destination));
  return { ...empty, sections, exception };
}
