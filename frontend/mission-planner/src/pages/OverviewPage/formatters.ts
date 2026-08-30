import type { POIETA } from '../../types/monitoring';

export type POISelectionInput = Omit<POIETA, 'eta_seconds'> & {
  readonly eta_seconds: number | null | undefined;
};

export type EtaUrgency =
  | { readonly state: 'critical'; readonly label: 'Most urgent' }
  | { readonly state: 'warning'; readonly label: 'High' }
  | { readonly state: 'caution'; readonly label: 'Moderate' }
  | { readonly state: 'normal'; readonly label: 'Normal' }
  | { readonly state: 'unavailable'; readonly label: 'Unavailable' };

export type ThresholdState =
  | { readonly state: 'ok'; readonly label: 'Normal' }
  | { readonly state: 'warning'; readonly label: 'Warning' }
  | { readonly state: 'critical'; readonly label: 'Critical' }
  | { readonly state: 'unavailable'; readonly label: 'Unavailable' };

export type ObstructionClassification = ThresholdState & {
  readonly displayValue: number | null;
  readonly outOfDisplayRange: boolean;
};

const UNAVAILABLE = '—';
const UNAVAILABLE_THRESHOLD = {
  state: 'unavailable',
  label: 'Unavailable',
} as const;

export function selectApplicablePOIs<T extends POISelectionInput>(
  pois: readonly T[]
): readonly T[] {
  return pois
    .map((poi, index) => ({ poi, index, eta: availableEta(poi.eta_seconds) }))
    .filter(
      ({ poi }) =>
        poi.route_aware_status !== 'already_passed' &&
        poi.course_status !== 'behind'
    )
    .sort((left, right) => {
      if (left.eta !== null && right.eta !== null) {
        return left.eta === right.eta
          ? left.index - right.index
          : left.eta - right.eta;
      }
      if (left.eta !== null) return -1;
      if (right.eta !== null) return 1;
      return left.index - right.index;
    })
    .slice(0, 5)
    .map(({ poi }) => poi);
}

export function classifyEtaUrgency(
  etaSeconds: number | null | undefined
): EtaUrgency {
  if (!isFiniteNumber(etaSeconds) || etaSeconds < 0) {
    return { state: 'unavailable', label: 'Unavailable' };
  }
  if (etaSeconds < 900) return { state: 'critical', label: 'Most urgent' };
  if (etaSeconds < 1800) return { state: 'warning', label: 'High' };
  if (etaSeconds < 3600) return { state: 'caution', label: 'Moderate' };
  return { state: 'normal', label: 'Normal' };
}

export function formatETA(value: number | null | undefined): string {
  if (!isFiniteNumber(value) || value < 0) return UNAVAILABLE;
  let seconds = roundAway(value);
  if (seconds === 0) return '0s';
  const days = Math.trunc(seconds / 86_400);
  seconds -= days * 86_400;
  const hours = Math.trunc(seconds / 3_600);
  seconds -= hours * 3_600;
  const minutes = Math.trunc(seconds / 60);
  seconds -= minutes * 60;
  return [
    days > 0 ? `${days}d` : null,
    hours > 0 ? `${hours}h` : null,
    minutes > 0 ? `${minutes}m` : null,
    seconds > 0 ? `${seconds}s` : null,
  ]
    .filter((part): part is string => part !== null)
    .join(' ');
}

export function formatLatencyMs(value: number | null | undefined): string {
  return isFiniteNumber(value) && value >= 0
    ? `${formatOneDecimal(value)} ms`
    : UNAVAILABLE;
}

export function formatThroughputMbps(value: number | null | undefined): string {
  return isFiniteNumber(value)
    ? `${formatOneDecimal(value)} Mbps`
    : UNAVAILABLE;
}

export function formatPercent(value: number | null | undefined): string {
  return isFiniteNumber(value) && value >= 0 && value <= 100
    ? `${formatOneDecimal(value)}%`
    : UNAVAILABLE;
}

export function formatCoordinates(latitude: number, longitude: number): string {
  if (!isValidLatitude(latitude) || !isValidLongitude(longitude))
    return UNAVAILABLE;
  return `${positiveZero(latitude).toFixed(4)}, ${positiveZero(
    longitude
  ).toFixed(4)}`;
}

export function formatAltitudeMeters(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return UNAVAILABLE;
  return `${formatIntegerGroups(roundAway(value))} m`;
}

export function formatPosition(
  latitude: number,
  longitude: number,
  altitude: number | null | undefined
): string {
  const coordinates = formatCoordinates(latitude, longitude);
  return coordinates === UNAVAILABLE
    ? UNAVAILABLE
    : `${coordinates} at ${formatAltitudeMeters(altitude)}`;
}

export function classifyLatency(
  value: number | null | undefined
): ThresholdState {
  return classifyThreshold(value, 100, 200, false);
}

export function classifyPacketLoss(
  value: number | null | undefined
): ThresholdState {
  return classifyThreshold(value, 2, 5, true);
}

export function classifyObstruction(
  value: number | null | undefined
): ObstructionClassification {
  if (!isFiniteNumber(value) || value < 0 || value > 100) {
    return {
      ...UNAVAILABLE_THRESHOLD,
      displayValue: null,
      outOfDisplayRange: false,
    };
  }
  return {
    ...classifyThreshold(value, 5, 10, true),
    displayValue: Math.min(value, 20),
    outOfDisplayRange: value > 20,
  };
}

function availableEta(value: number | null | undefined): number | null {
  return isFiniteNumber(value) && value >= 0 ? value : null;
}

function classifyThreshold(
  value: number | null | undefined,
  warning: number,
  critical: number,
  percent: boolean
): ThresholdState {
  if (!isFiniteNumber(value) || value < 0 || (percent && value > 100)) {
    return UNAVAILABLE_THRESHOLD;
  }
  if (value >= critical) return { state: 'critical', label: 'Critical' };
  if (value >= warning) return { state: 'warning', label: 'Warning' };
  return { state: 'ok', label: 'Normal' };
}

function formatOneDecimal(value: number): string {
  const rounded = positiveZero(roundAway(value * 10) / 10);
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

function roundAway(value: number): number {
  const sign = value < 0 ? -1 : 1;
  return positiveZero(sign * Math.floor(Math.abs(value) + 0.5));
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}

function formatIntegerGroups(value: number): string {
  const sign = value < 0 ? '-' : '';
  const digits = String(Math.abs(positiveZero(value)));
  const groups: string[] = [];
  for (let index = digits.length; index > 0; index -= 3) {
    groups.unshift(digits.slice(Math.max(0, index - 3), index));
  }
  return `${sign}${groups.join(',')}`;
}

function isValidLatitude(value: number): boolean {
  return isFiniteNumber(value) && value >= -90 && value <= 90;
}

function isValidLongitude(value: number): boolean {
  return isFiniteNumber(value) && value >= -180 && value <= 180;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
