import type { OverviewUpcomingPoi } from '@/services/overview-upcoming-pois';

const URGENCY_STOPS = [
  { remainingMs: 0, color: '#ef4444' },
  { remainingMs: 15 * 60 * 1000, color: '#f28b2d' },
  { remainingMs: 30 * 60 * 1000, color: '#facc15' },
  { remainingMs: 45 * 60 * 1000, color: '#8fd13a' },
  { remainingMs: 60 * 60 * 1000, color: '#22c55e' },
] as const;
const UNAVAILABLE_URGENCY_COLOR = '#64748b';

function interpolateHexColor(start: string, end: string, progress: number): string {
  const channels = [1, 3, 5].map((offset) => {
    const startChannel = Number.parseInt(start.slice(offset, offset + 2), 16);
    const endChannel = Number.parseInt(end.slice(offset, offset + 2), 16);
    return Math.round(startChannel + (endChannel - startChannel) * progress)
      .toString(16)
      .padStart(2, '0');
  });

  return `#${channels.join('')}`;
}

export function urgencyColor(
  estimatedArrivalTime: string | null,
  now: Date
): string {
  if (estimatedArrivalTime === null) {
    return UNAVAILABLE_URGENCY_COLOR;
  }

  const estimatedMs = Date.parse(estimatedArrivalTime);
  if (!Number.isFinite(estimatedMs)) {
    return UNAVAILABLE_URGENCY_COLOR;
  }

  const remainingMs = estimatedMs - now.valueOf();
  if (remainingMs <= URGENCY_STOPS[0].remainingMs) {
    return URGENCY_STOPS[0].color;
  }

  const lastStop = URGENCY_STOPS[URGENCY_STOPS.length - 1];
  if (remainingMs >= lastStop.remainingMs) {
    return lastStop.color;
  }

  const upperIndex = URGENCY_STOPS.findIndex(
    ({ remainingMs: stopRemainingMs }) => stopRemainingMs >= remainingMs
  );
  const lower = URGENCY_STOPS[upperIndex - 1];
  const upper = URGENCY_STOPS[upperIndex];
  const progress =
    (remainingMs - lower.remainingMs) /
    (upper.remainingMs - lower.remainingMs);

  return interpolateHexColor(lower.color, upper.color, progress);
}

export function overviewPoiView(
  records: OverviewUpcomingPoi[],
  now: Date
): { markers: OverviewUpcomingPoi[]; topFive: OverviewUpcomingPoi[] } {
  void now;

  return {
    markers: records.filter(
      ({ latitude, longitude, map_retained }) =>
        map_retained && Number.isFinite(latitude) && Number.isFinite(longitude)
    ),
    topFive: records.filter(({ upcoming }) => upcoming).slice(0, 5),
  };
}
