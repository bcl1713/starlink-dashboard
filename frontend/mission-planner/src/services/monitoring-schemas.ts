import { z } from 'zod';

import {
  OverviewDataValidationError,
  type OverviewDataSource,
  type RainViewerRadarTile,
} from '../types/monitoring';
import {
  awareTimestampSchema as awareTimestamp,
  azimuthSchema as azimuth,
  finiteNumberSchema as finite,
  isStrictlyChronological,
  latitudeSchema as latitude,
  longitudeSchema as longitude,
  nonNegativeNumberSchema as nonNegative,
  percentSchema as percent,
} from './monitoring-validation';
const issue = (ctx: z.RefinementCtx, message: string) =>
  ctx.addIssue({ code: 'custom', message });

const statusSchema = z.strictObject({
  timestamp: awareTimestamp,
  position: z.strictObject({
    latitude,
    longitude,
    altitude: finite,
    speed: nonNegative,
    heading: azimuth,
  }),
  network: z.strictObject({
    latency_ms: nonNegative,
    throughput_down_mbps: nonNegative,
    throughput_up_mbps: nonNegative,
    packet_loss_percent: percent,
  }),
  obstruction: z.strictObject({ obstruction_percent: percent }),
  environmental: z.strictObject({
    signal_quality_percent: percent,
    uptime_seconds: nonNegative,
    temperature_celsius: finite.nullable(),
  }),
});

const historySeriesNames = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

const historySampleSchema = z.strictObject({
  timestamp: awareTimestamp,
  value: finite.nullable(),
});

const historySeriesSchema = z.strictObject({
  metric: z.enum(historySeriesNames),
  samples: z.array(historySampleSchema).superRefine((samples, ctx) => {
    const timestamps = samples.map((sample) => sample.timestamp);
    if (!isStrictlyChronological(timestamps)) {
      issue(ctx, 'samples must be chronological');
    }
  }),
});

const monitoringHistorySchema = z
  .strictObject({
    generated_at: awareTimestamp,
    window_start: awareTimestamp,
    window_end: awareTimestamp,
    range_seconds: z.number().int().min(60).max(3600),
    step_seconds: z.number().int().min(1).max(60),
    series: z.array(historySeriesSchema).length(6),
  })
  .superRefine((value, ctx) => {
    value.series.forEach((series, index) => {
      if (series.metric !== historySeriesNames[index]) {
        issue(ctx, 'series metrics must match required order');
      }
    });
  });

const groundEntryPointSchema = z
  .strictObject({
    available: z.boolean(),
    observed_at: awareTimestamp.nullable(),
    generated_at: awareTimestamp,
    display: z.string().nullable(),
    city: z.string().nullable(),
    region: z.string().nullable(),
    country: z.string().nullable(),
    latitude: latitude.nullable(),
    longitude: longitude.nullable(),
  })
  .superRefine((value, ctx) => {
    if (!value.available) {
      for (const key of nullableGepFields) {
        if (value[key] !== null) issue(ctx, `${key} must be null`);
      }
      return;
    }
    for (const key of requiredGepFields) {
      if (value[key] === null) issue(ctx, `${key} is required`);
    }
    if (value.latitude === null || value.longitude === null) {
      issue(ctx, 'coordinates are required together');
    }
  });

const nullableGepFields = [
  'observed_at',
  'display',
  'city',
  'region',
  'country',
  'latitude',
  'longitude',
] as const;
const requiredGepFields = [
  'observed_at',
  'display',
  'city',
  'region',
  'country',
] as const;

const routeCoordinateSchema = z.strictObject({
  latitude,
  longitude,
  altitude_meters: finite.nullable(),
  sequence: finite,
});

const routeCoordinatesSchema = z
  .strictObject({
    route_id: z.string().nullable(),
    route_name: z.string().nullable(),
    revision_at: awareTimestamp.nullable(),
    generated_at: awareTimestamp,
    total: z.number().int().min(0),
    coordinates: z.array(routeCoordinateSchema),
  })
  .superRefine((value, ctx) => {
    if (value.total !== value.coordinates.length) {
      issue(ctx, 'total must equal coordinates length');
    }
  });

const routeAwareStatuses = [
  'ahead_on_route',
  'already_passed',
  'not_on_route',
  'pre_departure',
] as const;

const poiEtaSchema = z
  .strictObject({
    poi_id: z.string(),
    name: z.string(),
    latitude,
    longitude,
    category: z.string().nullable(),
    icon: z.string(),
    active: z.boolean(),
    eta_seconds: finite,
    eta_type: z.enum(['anticipated', 'estimated']),
    is_pre_departure: z.boolean(),
    flight_phase: z
      .enum(['pre_departure', 'in_flight', 'post_arrival'])
      .nullable(),
    distance_meters: nonNegative,
    bearing_degrees: azimuth.nullable(),
    course_status: z
      .enum(['on_course', 'slightly_off', 'off_track', 'behind'])
      .nullable(),
    is_on_active_route: z.boolean(),
    projected_latitude: latitude.nullable(),
    projected_longitude: longitude.nullable(),
    projected_waypoint_index: z.number().int().min(0).nullable(),
    projected_route_progress: percent.nullable(),
    route_aware_status: z.enum(routeAwareStatuses).nullable(),
  })
  .superRefine((value, ctx) => {
    if (
      (value.projected_latitude === null) !==
      (value.projected_longitude === null)
    ) {
      issue(ctx, 'projected coordinates are required together');
    }
  });

const poiEtaResponseSchema = z
  .strictObject({
    pois: z.array(poiEtaSchema),
    total: z.number().int().min(0),
    timestamp: awareTimestamp,
  })
  .superRefine((value, ctx) => {
    if (value.total !== value.pois.length)
      issue(ctx, 'total must equal pois length');
  });

const xLinkState = z.enum(['normal', 'warning']);
const xLinkColor = z.enum(['green', 'yellow']);
const xLinkCore = {
  satellite_id: z.string(),
  state: xLinkState,
  color: xLinkColor,
  relative_azimuth_degrees: azimuth,
  in_forbidden_window: z.boolean(),
};

const xLinkCoordinateSchema = z.strictObject({
  ...xLinkCore,
  point: z.enum(['aircraft', 'satellite']),
  sequence: z.number().int().min(0),
  latitude,
  longitude,
  observed_at: awareTimestamp.nullable(),
});

const xLinkSegmentSchema = z.strictObject({
  ...xLinkCore,
  coordinates: z.array(xLinkCoordinateSchema),
});

const xLinkHandoffSchema = z.strictObject({
  phase: z.enum(['outside', 'in_handoff_zone', 'committed']),
  transition_id: z.string().nullable(),
  transition_satellite_id: z.string().nullable(),
  radius_meters: nonNegative,
  distance_to_transition_meters: nonNegative.nullable(),
  in_handoff_zone: z.boolean(),
  route_progress_percent: percent.nullable(),
  transition_progress_percent: percent.nullable(),
});

const activeXLinkSchema = z
  .strictObject({
    coordinates: z.array(xLinkCoordinateSchema),
    links: z.array(xLinkSegmentSchema),
    total: z.number().int().min(0),
    satellite_id: z.string().nullable(),
    pending_satellite_id: z.string().nullable(),
    handoff: xLinkHandoffSchema,
    state: xLinkState.nullable(),
    color: xLinkColor.nullable(),
    relative_azimuth_degrees: azimuth.nullable(),
    in_forbidden_window: z.boolean().nullable(),
    observed_at: awareTimestamp.nullable(),
    generated_at: awareTimestamp,
  })
  .superRefine((value, ctx) => {
    if (value.total !== value.coordinates.length) {
      issue(ctx, 'total must equal coordinates length');
    }
  });

function parseOverviewData<T>(
  schema: z.ZodType<T>,
  data: unknown,
  source: OverviewDataSource
): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new OverviewDataValidationError(source);
  return parsed.data;
}

export const parseStatus = (data: unknown) =>
    parseOverviewData(statusSchema, data, 'status'),
  parseMonitoringHistory = (data: unknown) =>
    parseOverviewData(monitoringHistorySchema, data, 'monitoring-history'),
  parseGroundEntryPoint = (data: unknown) =>
    parseOverviewData(groundEntryPointSchema, data, 'ground-entry-point'),
  parseRouteCoordinates = (data: unknown) =>
    parseOverviewData(routeCoordinatesSchema, data, 'route-coordinates'),
  parsePOIETAs = (data: unknown) =>
    parseOverviewData(poiEtaResponseSchema, data, 'poi-etas'),
  parseActiveXLink = (data: unknown) =>
    parseOverviewData(activeXLinkSchema, data, 'active-x-link');

export function parseRainViewerRadarTile(
  data: unknown,
  headers: unknown
): RainViewerRadarTile {
  const frameTimestamp = readHeader(headers, 'x-radar-frame-timestamp');
  const timestampValue =
    frameTimestamp === undefined ? NaN : Number(frameTimestamp);
  const valid =
    data instanceof ArrayBuffer &&
    data.byteLength >= 8 &&
    data.byteLength <= 2 * 1024 * 1024 &&
    matchesPngSignature(data) &&
    normalizedContentType(headers) === 'image/png' &&
    frameTimestamp !== undefined &&
    /^(0|[1-9][0-9]*)$/.test(frameTimestamp) &&
    Number.isSafeInteger(timestampValue) &&
    timestampValue >= 946684800 &&
    timestampValue <= 4102444800;

  if (!valid) throw new OverviewDataValidationError('rainviewer-radar-tile');
  return { bytes: data, frameTimestamp };
}

export function validateRadarXYZ(z: number, x: number, y: number): void {
  const max = 2 ** z;
  if (
    ![z, x, y].every(Number.isInteger) ||
    z < 0 ||
    z > 7 ||
    x < 0 ||
    y < 0 ||
    x >= max ||
    y >= max
  ) {
    throw new OverviewDataValidationError('rainviewer-radar-tile');
  }
}

function matchesPngSignature(data: ArrayBuffer): boolean {
  const bytes = new Uint8Array(data, 0, 8);
  return [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a].every(
    (byte, index) => bytes[index] === byte
  );
}

function normalizedContentType(headers: unknown): string | undefined {
  return readHeader(headers, 'content-type')
    ?.split(';')[0]
    ?.trim()
    .toLowerCase();
}

function readHeader(headers: unknown, name: string): string | undefined {
  const get = (headers as { get?: unknown } | null)?.get;
  if (typeof get === 'function') {
    const value = get.call(headers, name) as unknown;
    if (typeof value === 'string') return value;
  }
  if (!headers || typeof headers !== 'object') return undefined;
  const value = (headers as Record<string, unknown>)[name];
  return typeof value === 'string' ? value : undefined;
}
