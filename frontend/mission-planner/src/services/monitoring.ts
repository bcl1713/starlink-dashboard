import { z } from 'zod';
import { getJson } from './boundedJson';

export { getJson, MAX_JSON_RESPONSE_BYTES } from './boundedJson';

const MAX_HISTORY_POINTS_PER_SERIES = 1801;
const MAX_HISTORY_POINTS_TOTAL = 7200;
const MAX_POIS = 100;
const MAX_EXTERNAL_TEXT = 200;
const finite = z.number().finite();
const instant = z.string().datetime({ offset: true });
const text = z.string().max(MAX_EXTERNAL_TEXT);
const coordinate = z.strictObject({
  latitude: finite.min(-90).max(90),
  longitude: finite.min(-180).max(180),
});

const statusSchema = z
  .strictObject({
    source: z.enum(['simulation', 'live']),
    timestamp: instant,
    observed_at: instant,
    received_at: instant,
    position: coordinate.extend({
      altitude: finite,
      speed: finite.nonnegative(),
      heading: finite.min(0).max(360),
    }),
    network: z.strictObject({
      latency_ms: finite.nonnegative(),
      throughput_down_mbps: finite.nonnegative(),
      throughput_up_mbps: finite.nonnegative(),
      packet_loss_percent: finite.min(0).max(100),
    }),
    obstruction: z.strictObject({
      obstruction_percent: finite.min(0).max(100),
    }),
    environmental: z.strictObject({
      signal_quality_percent: finite.min(0).max(100),
      uptime_seconds: finite.nonnegative(),
      temperature_celsius: finite.nullable(),
    }),
  })
  .superRefine((value, context) => {
    const observed = Date.parse(value.observed_at);
    if (Date.parse(value.timestamp) !== observed) {
      context.addIssue({
        code: 'custom',
        message: 'legacy timestamp differs from observation',
        path: ['timestamp'],
      });
    }
    if (Date.parse(value.received_at) < observed) {
      context.addIssue({
        code: 'custom',
        message: 'receipt precedes observation',
        path: ['received_at'],
      });
    }
  });

export const metricOrder = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;
type Metric = (typeof metricOrder)[number];

const sampleSchema = z.strictObject({
  timestamp: instant,
  value: finite.nullable(),
});
const historySchema = z
  .strictObject({
    generated_at: instant,
    window_start: instant,
    window_end: instant,
    range_seconds: z.number().int().min(60).max(1800),
    step_seconds: z.number().int().min(1).max(30),
    series: z
      .array(
        z.strictObject({
          metric: z.enum(metricOrder),
          samples: z.array(sampleSchema).max(MAX_HISTORY_POINTS_PER_SERIES),
        })
      )
      .length(metricOrder.length),
  })
  .superRefine((value, context) => {
    const start = Date.parse(value.window_start);
    const end = Date.parse(value.window_end);
    if (start > end) {
      context.addIssue({ code: 'custom', message: 'invalid history window' });
      return;
    }
    if (end - start !== value.range_seconds * 1000) {
      context.addIssue({
        code: 'custom',
        message: 'history range disagrees with window',
        path: ['range_seconds'],
      });
    }
    if (Date.parse(value.generated_at) < end) {
      context.addIssue({
        code: 'custom',
        message: 'history generation precedes window end',
        path: ['generated_at'],
      });
    }
    value.series.forEach((series, seriesIndex) => {
      if (series.metric !== metricOrder[seriesIndex]) {
        context.addIssue({
          code: 'custom',
          message: 'invalid history series order',
          path: ['series', seriesIndex, 'metric'],
        });
      }
      let previous = Number.NEGATIVE_INFINITY;
      series.samples.forEach((sample, sampleIndex) => {
        const timestamp = Date.parse(sample.timestamp);
        if (timestamp < start || timestamp > end || timestamp <= previous) {
          context.addIssue({
            code: 'custom',
            message: 'invalid history sample timestamp',
            path: ['series', seriesIndex, 'samples', sampleIndex, 'timestamp'],
          });
        }
        previous = timestamp;
        if (
          sample.value !== null &&
          !validMetricValue(series.metric, sample.value)
        ) {
          context.addIssue({
            code: 'custom',
            message: 'invalid history metric value',
            path: ['series', seriesIndex, 'samples', sampleIndex, 'value'],
          });
        }
      });
    });
  });

const gepSchema = z
  .strictObject({
    available: z.boolean(),
    observed_at: instant.nullable(),
    generated_at: instant,
    display: text.nullable(),
    city: text.nullable(),
    region: text.nullable(),
    country: text.nullable(),
    latitude: finite.min(-90).max(90).nullable(),
    longitude: finite.min(-180).max(180).nullable(),
  })
  .refine(
    (value) =>
      value.observed_at === null ||
      Date.parse(value.observed_at) <= Date.parse(value.generated_at),
    {
      message: 'GEP observation follows generation',
      path: ['observed_at'],
    }
  );

const etaSeconds = finite.refine((value) => value === -1 || value >= 0, {
  message: 'ETA must be -1 or nonnegative',
});
const poiResponseItemSchema = coordinate.extend({
  poi_id: text.min(1),
  name: text.min(1),
  category: text.nullable(),
  icon: text.min(1),
  active: z.boolean(),
  eta_seconds: etaSeconds,
  eta_type: z.enum(['anticipated', 'estimated']),
  is_pre_departure: z.boolean(),
  flight_phase: z
    .enum(['pre_departure', 'in_flight', 'post_arrival'])
    .nullable(),
  distance_meters: finite.nonnegative(),
  bearing_degrees: finite.min(0).max(360).nullable(),
  course_status: z
    .enum(['on_course', 'slightly_off', 'off_track', 'behind'])
    .nullable(),
  is_on_active_route: z.boolean(),
  projected_latitude: finite.min(-90).max(90).nullable(),
  projected_longitude: finite.min(-180).max(180).nullable(),
  projected_waypoint_index: z.number().int().nonnegative().nullable(),
  projected_route_progress: finite.min(0).max(100).nullable(),
  route_aware_status: z
    .enum(['ahead_on_route', 'already_passed', 'not_on_route', 'pre_departure'])
    .nullable(),
});
const poiSchema = coordinate.extend({
  poi_id: text.min(1),
  name: text.min(1),
  category: text.nullable(),
  eta_seconds: etaSeconds,
  distance_meters: finite.nonnegative(),
  active: z.boolean(),
});
const poiResponseSchema = z
  .strictObject({
    pois: z.array(poiResponseItemSchema).max(MAX_POIS),
    total: z.number().int().nonnegative().max(MAX_POIS),
    timestamp: instant,
  })
  .refine((value) => value.total === value.pois.length, {
    message: 'POI total does not match collection length',
    path: ['total'],
  });

export type StatusData = z.infer<typeof statusSchema>;
export type MonitoringHistory = z.infer<typeof historySchema>;
export type GroundEntryPoint = z.infer<typeof gepSchema>;
export type ApplicablePoi = z.infer<typeof poiSchema>;

export const statusUrl = '/api/status';
export const historyUrl = '/api/monitoring/history';
export const groundEntryPointUrl = '/api/monitoring/ground-entry-point';
export const poiUrl = '/api/pois/etas';

export const parseStatus = (value: unknown): StatusData =>
  statusSchema.parse(value);
export const parseHistory = (value: unknown): MonitoringHistory => {
  assertBoundedHistory(value);
  return historySchema.parse(value);
};
export const parseGroundEntryPoint = (value: unknown): GroundEntryPoint =>
  gepSchema.parse(value);
export const parseApplicablePois = (value: unknown): ApplicablePoi[] => {
  assertBoundedPois(value);
  return poiResponseSchema.parse(value).pois.map((poi) =>
    poiSchema.parse({
      poi_id: poi.poi_id,
      name: poi.name,
      category: poi.category,
      eta_seconds: poi.eta_seconds,
      distance_meters: poi.distance_meters,
      active: poi.active,
      latitude: poi.latitude,
      longitude: poi.longitude,
    })
  );
};

function assertBoundedHistory(value: unknown): void {
  if (!isRecord(value) || !Array.isArray(value.series)) return;
  let total = 0;
  for (const series of value.series) {
    if (!isRecord(series) || !Array.isArray(series.samples)) continue;
    if (series.samples.length > MAX_HISTORY_POINTS_PER_SERIES) {
      throw new Error('History response exceeds point budget');
    }
    total += series.samples.length;
    if (total > MAX_HISTORY_POINTS_TOTAL) {
      throw new Error('History response exceeds aggregate point budget');
    }
  }
}

function assertBoundedPois(value: unknown): void {
  if (
    isRecord(value) &&
    Array.isArray(value.pois) &&
    value.pois.length > MAX_POIS
  ) {
    throw new Error('POI response exceeds item budget');
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function validMetricValue(metric: Metric, value: number): boolean {
  if (metric === 'latitude_degrees') return value >= -90 && value <= 90;
  if (metric === 'longitude_degrees') return value >= -180 && value <= 180;
  if (metric === 'packet_loss_percent') return value >= 0 && value <= 100;
  return value >= 0;
}

export async function fetchStatus(signal?: AbortSignal): Promise<StatusData> {
  return parseStatus(await getJson(statusUrl, signal));
}

export async function fetchHistory(
  signal?: AbortSignal
): Promise<MonitoringHistory> {
  return parseHistory(await getJson(historyUrl, signal));
}

export async function fetchGroundEntryPoint(
  signal?: AbortSignal
): Promise<GroundEntryPoint> {
  return parseGroundEntryPoint(await getJson(groundEntryPointUrl, signal));
}

export async function fetchApplicablePois(
  signal?: AbortSignal
): Promise<ApplicablePoi[]> {
  return parseApplicablePois(await getJson(poiUrl, signal))
    .filter((poi) => poi.active !== false)
    .sort((left, right) => left.eta_seconds - right.eta_seconds)
    .slice(0, 5);
}
