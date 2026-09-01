import { awareTimestampSchema } from '../../services/monitoring-validation';
import type { ActiveXLink, RouteCoordinates } from '../../types/monitoring';
import type { PositionHistoryPoint } from './history';

export interface OverviewGeometryPoint {
  readonly latitude: number;
  readonly longitude: number;
  readonly altitudeMeters: number | null;
  readonly timestamp: string | null;
}

export type GeometryInputPoint = OverviewGeometryPoint | null;
type ParsedInstant = Readonly<{ seconds: bigint; fraction: string }>;

export interface SplitActiveLinkSegment {
  readonly link: ActiveXLink['links'][number];
  readonly segments: readonly (readonly OverviewGeometryPoint[])[];
}

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.([0-9]+))?)?(Z|[+-]\d{2}:\d{2})$/;
const unixEpochDay = daysFromCivil('1970', '01', '01');

export function normalizeLongitude(longitude: number): number {
  if (!Number.isFinite(longitude)) throw new RangeError('Invalid longitude');
  const normalized = ((((longitude + 180) % 360) + 360) % 360) - 180;
  return Object.is(normalized, -0) ? 0 : normalized;
}

export function splitAtInternationalDateLine(
  points: readonly GeometryInputPoint[]
): readonly (readonly OverviewGeometryPoint[])[] {
  const segments: OverviewGeometryPoint[][] = [];
  let current: OverviewGeometryPoint[] = [];
  let previous: OverviewGeometryPoint | null = null;
  const flush = () => {
    if (current.length > 0) segments.push(current);
    current = [];
    previous = null;
  };
  for (const rawPoint of points) {
    const point = normalizePoint(rawPoint);
    if (point === null) {
      flush();
      continue;
    }
    if (previous === null) {
      current.push(point);
      previous = point;
      continue;
    }
    const crossing = buildCrossing(previous, point);
    if (crossing === null) {
      current.push(point);
    } else {
      if (crossing.fraction !== 0) current.push(crossing.departure);
      flush();
      current.push(crossing.fraction === 1 ? point : crossing.opposite);
      if (crossing.fraction !== 1) current.push(point);
    }
    previous = point;
  }
  flush();
  return segments;
}

export function adaptRouteCoordinates(
  route: RouteCoordinates
): readonly OverviewGeometryPoint[] {
  return route.coordinates.flatMap((coordinate) => {
    if (
      !Number.isFinite(coordinate.latitude) ||
      !Number.isFinite(coordinate.longitude)
    ) {
      return [];
    }
    return [
      {
        latitude: positiveZero(coordinate.latitude),
        longitude: normalizeLongitude(coordinate.longitude),
        altitudeMeters: finiteValueOrNull(coordinate.altitude_meters),
        timestamp: null,
      },
    ];
  });
}

export function adaptPositionHistory(
  points: readonly PositionHistoryPoint[]
): readonly OverviewGeometryPoint[] {
  return points.map((point) => ({
    latitude: positiveZero(point.latitude),
    longitude: normalizeLongitude(point.longitude),
    altitudeMeters: finiteValueOrNull(point.altitudeMeters),
    timestamp: point.timestamp,
  }));
}

export function adaptActiveLinkSegment(
  segment: ActiveXLink['links'][number]
): readonly OverviewGeometryPoint[] {
  return segment.coordinates.flatMap((coordinate) => {
    if (
      !Number.isFinite(coordinate.latitude) ||
      !Number.isFinite(coordinate.longitude)
    ) {
      return [];
    }
    return [
      {
        latitude: positiveZero(coordinate.latitude),
        longitude: normalizeLongitude(coordinate.longitude),
        altitudeMeters: null,
        timestamp: coordinate.observed_at,
      },
    ];
  });
}

export function splitActiveLinkSegments(
  links: ReadonlyArray<ActiveXLink['links'][number]>
): readonly SplitActiveLinkSegment[] {
  return links.map((link) => ({
    link,
    segments: splitAtInternationalDateLine(adaptActiveLinkSegment(link)),
  }));
}

function normalizePoint(
  point: GeometryInputPoint
): OverviewGeometryPoint | null {
  if (
    point === null ||
    !isFiniteNumber(point.latitude) ||
    point.latitude < -90 ||
    point.latitude > 90 ||
    !isFiniteNumber(point.longitude)
  ) {
    return null;
  }
  return {
    latitude: positiveZero(point.latitude),
    longitude: normalizeLongitude(point.longitude),
    altitudeMeters: isFiniteNumber(point.altitudeMeters)
      ? positiveZero(point.altitudeMeters)
      : null,
    timestamp: point.timestamp,
  };
}

function buildCrossing(
  start: OverviewGeometryPoint,
  end: OverviewGeometryPoint
): {
  readonly fraction: number;
  readonly departure: OverviewGeometryPoint;
  readonly opposite: OverviewGeometryPoint;
} | null {
  const delta = end.longitude - start.longitude;
  if (Math.abs(delta) <= 180) return null;
  const adjustedEnd = delta > 180 ? end.longitude - 360 : end.longitude + 360;
  const edge = adjustedEnd > start.longitude ? 180 : -180;
  const oppositeEdge = edge === 180 ? -180 : 180;
  const fraction = (edge - start.longitude) / (adjustedEnd - start.longitude);
  const synthetic = interpolatePoint(start, end, fraction, edge);
  return {
    fraction,
    departure: fraction === 0 ? start : synthetic,
    opposite:
      fraction === 1
        ? end
        : {
            ...synthetic,
            longitude: oppositeEdge,
          },
  };
}

function interpolatePoint(
  start: OverviewGeometryPoint,
  end: OverviewGeometryPoint,
  fraction: number,
  longitude: number
): OverviewGeometryPoint {
  const altitude =
    isFiniteNumber(start.altitudeMeters) && isFiniteNumber(end.altitudeMeters)
      ? interpolateFinite(start.altitudeMeters, end.altitudeMeters, fraction)
      : null;
  return {
    latitude: start.latitude + (end.latitude - start.latitude) * fraction,
    longitude,
    altitudeMeters: altitude === null ? null : positiveZero(altitude),
    timestamp: interpolateTimestamp(start.timestamp, end.timestamp, fraction),
  };
}

function interpolateTimestamp(
  start: string | null,
  end: string | null,
  fraction: number
): string | null {
  if (start === null || end === null) return null;
  const first = parseInstant(start);
  const second = parseInstant(end);
  if (first === null || second === null) return null;
  const milliseconds = interpolateMilliseconds(first, second, fraction);
  if (
    milliseconds < -8_640_000_000_000_000n ||
    milliseconds > 8_640_000_000_000_000n
  )
    return null;
  const iso = new Date(Number(milliseconds)).toISOString();
  return iso.endsWith('.000Z') ? `${iso.slice(0, -5)}Z` : iso;
}

function parseInstant(value: string): ParsedInstant | null {
  const match = timestampPattern.exec(value);
  if (!match || !awareTimestampSchema.safeParse(value).success) return null;
  const [, year, month, day, hour, minute, second, fraction = '', offset] =
    match;
  const seconds =
    (daysFromCivil(year, month, day) - unixEpochDay) * 86_400n +
    BigInt(hour) * 3_600n +
    BigInt(minute) * 60n +
    BigInt(second ?? '0') -
    (offset === 'Z' ? 0n : parseOffsetSeconds(offset));
  return { seconds, fraction: fraction.replace(/0+$/, '') };
}

function interpolateMilliseconds(
  start: ParsedInstant,
  end: ParsedInstant,
  fraction: number
): bigint {
  const weight = parseUnitDecimal(fraction);
  const width = Math.max(
    start.fraction.length,
    end.fraction.length,
    weight.scale
  );
  const scale = 10n ** BigInt(width);
  const startUnits = instantUnits(start, width);
  const endUnits = instantUnits(end, width);
  const numerator =
    startUnits * weight.denominator +
    (endUnits - startUnits) * weight.numerator;
  return (numerator * 1000n) / (weight.denominator * scale);
}

function instantUnits(instant: ParsedInstant, width: number): bigint {
  return (
    instant.seconds * 10n ** BigInt(width) +
    BigInt(instant.fraction.padEnd(width, '0') || '0')
  );
}

function parseUnitDecimal(value: number) {
  const match = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(String(value));
  if (!match) return { numerator: 0n, denominator: 1n, scale: 0 };
  const digits = `${match[1]}${match[2] ?? ''}`.replace(/^0+(?=\d)/, '');
  const scale = Math.max(0, (match[2]?.length ?? 0) - Number(match[3] ?? 0));
  const exponent = Number(match[3] ?? 0);
  return {
    numerator:
      scale === 0 ? BigInt(digits) * 10n ** BigInt(exponent) : BigInt(digits),
    denominator: 10n ** BigInt(scale),
    scale,
  };
}

function interpolateFinite(start: number, end: number, fraction: number) {
  if (fraction === 0) return positiveZero(start);
  if (fraction === 1) return positiveZero(end);
  if (start === end) return positiveZero(start);
  const delta = end - start;
  const result = Number.isFinite(delta)
    ? start + delta * fraction
    : start * (1 - fraction) + end * fraction;
  return Number.isFinite(result) ? positiveZero(result) : null;
}

function daysFromCivil(year: string, month: string, day: string): bigint {
  let adjustedYear = BigInt(year);
  const monthNumber = BigInt(month);
  if (monthNumber <= 2n) adjustedYear -= 1n;
  const era = floorDiv(adjustedYear, 400n);
  const yearOfEra = adjustedYear - era * 400n;
  const monthPrime = monthNumber + (monthNumber > 2n ? -3n : 9n);
  const dayOfYear = (153n * monthPrime + 2n) / 5n + BigInt(day) - 1n;
  const dayOfEra =
    yearOfEra * 365n + yearOfEra / 4n - yearOfEra / 100n + dayOfYear;
  return era * 146_097n + dayOfEra;
}

function floorDiv(dividend: bigint, divisor: bigint): bigint {
  const quotient = dividend / divisor;
  const remainder = dividend % divisor;
  return remainder < 0n ? quotient - 1n : quotient;
}

function parseOffsetSeconds(offset: string): bigint {
  const sign = offset[0] === '-' ? -1 : 1;
  return BigInt(
    sign * (Number(offset.slice(1, 3)) * 3600 + Number(offset.slice(4, 6)) * 60)
  );
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}

function finiteValueOrNull(value: number | null | undefined): number | null {
  return isFiniteNumber(value) ? positiveZero(value) : null;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
