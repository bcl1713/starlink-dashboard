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
  let seconds = roundDecimal(value, 0).units;
  if (seconds === 0n) return '0s';
  const days = seconds / 86_400n;
  seconds -= days * 86_400n;
  const hours = seconds / 3_600n;
  seconds -= hours * 3_600n;
  const minutes = seconds / 60n;
  seconds -= minutes * 60n;
  return [
    days > 0n ? `${days}d` : null,
    hours > 0n ? `${hours}h` : null,
    minutes > 0n ? `${minutes}m` : null,
    seconds > 0n ? `${seconds}s` : null,
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
  return `${formatIntegerGroups(value)} m`;
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
    displayValue: positiveZero(Math.min(value, 20)),
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
  const rounded = roundDecimal(value, 1);
  return formatRoundedDecimal(rounded, true);
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}

function formatIntegerGroups(value: number): string {
  const rounded = roundDecimal(value, 0);
  const sign = rounded.negative && rounded.units !== 0n ? '-' : '';
  const digits = String(rounded.units);
  const groups: string[] = [];
  for (let index = digits.length; index > 0; index -= 3) {
    groups.unshift(digits.slice(Math.max(0, index - 3), index));
  }
  return `${sign}${groups.join(',')}`;
}

function formatRoundedDecimal(
  rounded: { negative: boolean; units: bigint; places: number },
  trim: boolean
): string {
  const sign = rounded.negative && rounded.units !== 0n ? '-' : '';
  const raw = String(rounded.units).padStart(rounded.places + 1, '0');
  const whole = groupDigits(raw.slice(0, -rounded.places) || '0');
  if (rounded.places === 0) return `${sign}${whole}`;
  const fraction = raw.slice(-rounded.places);
  const suffix = trim ? fraction.replace(/0+$/, '') : fraction;
  return suffix ? `${sign}${whole}.${suffix}` : `${sign}${whole}`;
}

function groupDigits(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function roundDecimal(value: number, places: number) {
  const decimal = parseDecimal(value);
  const numerator = decimal.units * 10n ** BigInt(places);
  const denominator = 10n ** BigInt(decimal.scale);
  let units = numerator / denominator;
  if ((numerator % denominator) * 2n >= denominator) units += 1n;
  return { negative: decimal.negative, units, places };
}

function parseDecimal(value: number) {
  const text = String(Math.abs(value));
  const match = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(text);
  if (!match) return { negative: value < 0, units: 0n, scale: 0 };
  const digits = `${match[1]}${match[2] ?? ''}`.replace(/^0+(?=\d)/, '');
  const scale = (match[2]?.length ?? 0) - Number(match[3] ?? 0);
  if (scale <= 0) {
    return {
      negative: value < 0,
      units: BigInt(digits) * 10n ** BigInt(-scale),
      scale: 0,
    };
  }
  return { negative: value < 0, units: BigInt(digits), scale };
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
