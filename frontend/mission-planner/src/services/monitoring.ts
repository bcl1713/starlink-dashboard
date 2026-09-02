import { z } from 'zod';
import { getJson } from './boundedJson';
import { type ApplicablePoi, parseApplicablePois } from './monitoringPois';
import {
  compareInstants,
  coordinate,
  finite,
  instant,
  instantsDifferBySeconds,
  text,
} from './monitoringSchemaPrimitives';

export { getJson, MAX_JSON_RESPONSE_BYTES } from './boundedJson';
export { parseApplicablePois } from './monitoringPois';
export type { ApplicablePoi } from './monitoringPois';

const MAX_HISTORY_POINTS_PER_SERIES = 1801;
const MAX_HISTORY_POINTS_TOTAL = 7200;

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
    if (compareInstants(value.timestamp, value.observed_at) !== 0) {
      context.addIssue({
        code: 'custom',
        message: 'legacy timestamp differs from observation',
        path: ['timestamp'],
      });
    }
    if (compareInstants(value.received_at, value.observed_at) < 0) {
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
    if (compareInstants(value.window_start, value.window_end) > 0) {
      context.addIssue({ code: 'custom', message: 'invalid history window' });
      return;
    }
    if (
      !instantsDifferBySeconds(
        value.window_start,
        value.window_end,
        value.range_seconds
      )
    ) {
      context.addIssue({
        code: 'custom',
        message: 'history range disagrees with window',
        path: ['range_seconds'],
      });
    }
    if (compareInstants(value.generated_at, value.window_end) < 0) {
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
      let previous: string | undefined;
      series.samples.forEach((sample, sampleIndex) => {
        if (
          compareInstants(sample.timestamp, value.window_start) < 0 ||
          compareInstants(sample.timestamp, value.window_end) > 0 ||
          (previous !== undefined &&
            compareInstants(sample.timestamp, previous) <= 0)
        ) {
          context.addIssue({
            code: 'custom',
            message: 'invalid history sample timestamp',
            path: ['series', seriesIndex, 'samples', sampleIndex, 'timestamp'],
          });
        }
        previous = sample.timestamp;
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
      compareInstants(value.observed_at, value.generated_at) <= 0,
    {
      message: 'GEP observation follows generation',
      path: ['observed_at'],
    }
  );

export type StatusData = z.infer<typeof statusSchema>;
export type MonitoringHistory = z.infer<typeof historySchema>;
export type GroundEntryPoint = z.infer<typeof gepSchema>;

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
