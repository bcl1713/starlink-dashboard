import { z } from 'zod';

const finite = z.number().finite();
const instant = z.string().datetime({ offset: true });
const coordinate = z.object({
  latitude: finite.min(-90).max(90),
  longitude: finite.min(-180).max(180),
});

const statusSchema = z.object({
  source: z.enum(['simulation', 'live']),
  timestamp: instant,
  observed_at: instant,
  received_at: instant,
  position: coordinate.extend({
    altitude: finite,
    speed: finite.nonnegative(),
    heading: finite.min(0).max(360),
  }),
  network: z.object({
    latency_ms: finite.nonnegative(),
    throughput_down_mbps: finite.nonnegative(),
    throughput_up_mbps: finite.nonnegative(),
    packet_loss_percent: finite.min(0).max(100),
  }),
  obstruction: z.object({ obstruction_percent: finite.min(0).max(100) }),
  environmental: z.object({
    signal_quality_percent: finite.min(0).max(100),
    uptime_seconds: finite.nonnegative(),
    temperature_celsius: finite.nullable(),
  }),
});

const sampleSchema = z.object({ timestamp: instant, value: finite.nullable() });
const historySchema = z.object({
  generated_at: instant,
  window_start: instant,
  window_end: instant,
  range_seconds: z.number().int().min(60).max(1800),
  step_seconds: z.number().int().min(1).max(30),
  series: z.array(
    z.object({
      metric: z.enum([
        'latitude_degrees',
        'longitude_degrees',
        'latency_ms',
        'throughput_down_mbps',
        'throughput_up_mbps',
        'packet_loss_percent',
      ]),
      samples: z.array(sampleSchema).max(1801),
    })
  ),
});

const gepSchema = z.object({
  available: z.boolean(),
  observed_at: instant.nullable(),
  generated_at: instant,
  display: z.string().nullable(),
  city: z.string().nullable(),
  region: z.string().nullable(),
  country: z.string().nullable(),
  latitude: finite.min(-90).max(90).nullable(),
  longitude: finite.min(-180).max(180).nullable(),
});

const poiSchema = coordinate.extend({
  poi_id: z.string(),
  name: z.string(),
  category: z.string().nullable().optional(),
  eta_seconds: finite.nonnegative(),
  distance_meters: finite.nonnegative(),
  active: z.boolean().optional(),
});
const poiResponseSchema = z.object({ pois: z.array(poiSchema) });

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
export const parseHistory = (value: unknown): MonitoringHistory =>
  historySchema.parse(value);
export const parseGroundEntryPoint = (value: unknown): GroundEntryPoint =>
  gepSchema.parse(value);

export async function getJson(
  url: string,
  signal?: AbortSignal
): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  const relay = () => controller.abort();
  signal?.addEventListener('abort', relay, { once: true });
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return await response.json();
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', relay);
  }
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
  const parsed = poiResponseSchema.parse(await getJson(poiUrl, signal));
  return parsed.pois
    .filter((poi) => poi.active !== false)
    .sort((left, right) => left.eta_seconds - right.eta_seconds)
    .slice(0, 5);
}
