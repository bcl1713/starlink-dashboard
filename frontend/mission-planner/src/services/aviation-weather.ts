import { z } from 'zod';
import apiClient from './api-client';
import { weatherManifestSchema } from './overview-weather';

const integer = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const time = integer.nullable();
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const identifier = z.string().regex(/^[a-z0-9_-]{1,64}$/);
const finite = z.number().finite();
const attribution = z.strictObject({
  label: z.string().min(1).max(256),
  url: z
    .string()
    .max(2048)
    .regex(/^https:\/\/[^\s]+$/),
});
const verticalSchema = z.union([
  z.strictObject({ kind: z.literal('surface') }),
  z.strictObject({ kind: z.literal('not-applicable') }),
  z.strictObject({
    kind: z.literal('pressure'),
    pressure_pa: finite.positive().max(110000),
  }),
  z
    .strictObject({
      kind: z.literal('flight-level'),
      flight_level: integer.max(600),
      reference: z.literal('pressure-altitude-1013.25hpa'),
      derivation: z.enum(['native', 'isa-log-pressure-v1']),
      source_pressures_pa: z.array(finite).max(2),
    })
    .refine((v) =>
      v.derivation === 'native'
        ? v.source_pressures_pa.length === 0
        : v.source_pressures_pa.length === 2 &&
          v.source_pressures_pa[0] > 0 &&
          v.source_pressures_pa[0] < v.source_pressures_pa[1] &&
          v.source_pressures_pa[1] <= 110000
    ),
  z
    .strictObject({
      kind: z.literal('bounds'),
      lower: finite.nullable(),
      upper: finite.nullable(),
      unit: z.enum(['m', 'flight-level', 'unknown']),
      reference: z.enum(['MSL', 'AGL', 'FL', 'unknown']),
    })
    .refine(
      (v) =>
        (v.lower === null || v.upper === null || v.lower <= v.upper) &&
        (v.reference === 'FL') === (v.unit === 'flight-level') &&
        (v.reference === 'unknown') === (v.unit === 'unknown')
    ),
]);
const coverageSchema = z.strictObject({
  generation: z.string().min(1).max(128),
  expires_at_ms: integer,
  mask_encoding: z.enum([
    'feature-collection-v1',
    'uint8-validity-v1',
    'absence-rgba-v1',
  ]),
  missing_meaning: z.literal('unknown-not-clear'),
  feed_completeness: z.enum(['unknown', 'partial', 'complete']),
});
const payloadSchema = z.strictObject({
  path: z
    .string()
    .max(256)
    .regex(
      /^\/api\/aviation-weather\/v1\/products\/[a-f0-9]{64}\/[a-z0-9_-]+\.(json|bin)$/
    ),
  sha256: hash,
  content_type: z.enum([
    'application/json',
    'application/geo+json',
    'application/octet-stream',
  ]),
  encoded_bytes: integer.positive().max(16 * 1024 ** 2),
  decoded_bytes: integer.positive().max(32 * 1024 ** 2),
  gpu_bytes: integer.max(16 * 1024 ** 2),
});
const componentSchema = z
  .strictObject({
    quantity: z.enum([
      'air-temperature',
      'wind-east',
      'wind-north',
      'brightness-temperature',
    ]),
    unit: z.enum(['K', 'm/s']),
    scale: finite.positive(),
    offset: finite,
  })
  .refine((v) => v.unit === (v.quantity.startsWith('wind-') ? 'm/s' : 'K'));
const gridSchema = z
  .strictObject({
    width: integer.min(2).max(720),
    height: integer.min(2).max(361),
    longitude_start: z.literal(-180),
    latitude_start: z.literal(90),
    longitude_step: finite.positive(),
    latitude_step: finite.negative(),
    mask_encoding: z.literal('uint8-validity-v1'),
    components: z.array(componentSchema).min(1).max(3),
  })
  .refine(
    (v) =>
      Math.abs(v.width * v.longitude_step - 360) <= 1e-9 &&
      Math.abs((v.height - 1) * v.latitude_step + 180) <= 1e-9 &&
      new Set(v.components.map((c) => c.quantity)).size === v.components.length
  );

export const weatherProductSchema = z
  .strictObject({
    state: z.enum(['off', 'ready', 'stale', 'unavailable']),
    layer_id: identifier,
    product_type: z.enum([
      'observed-precipitation',
      'metar-speci',
      'taf',
      'international-sigmet',
      'winds',
      'air-temperature',
      'satellite-ir',
    ]),
    representation: z.enum([
      'xyz-rgba-pair-v1',
      'station-v1',
      'advisory-v1',
      'latlon-grid-v1',
    ]),
    source_id: identifier,
    provenance: z.string().min(1).max(512),
    attribution: z.array(attribution).min(1).max(8),
    time_kind: z.enum(['observation', 'forecast', 'analysis']),
    method_kind: z.enum(['reported', 'sensor', 'numerical-model', 'derived']),
    observed_at_ms: time,
    issued_at_ms: time,
    scan_start_ms: time,
    scan_end_ms: time,
    validity_kind: z.enum(['instant', 'interval', 'collection']),
    valid_at_ms: time,
    valid_from_ms: time,
    valid_to_ms: time,
    run_at_ms: time,
    lead_seconds: integer.max(604800).nullable(),
    vertical: verticalSchema,
    coverage: coverageSchema.nullable(),
    generated_at_ms: integer,
    retrieved_at_ms: time,
    fresh_until_ms: time,
    expires_at_ms: time,
    product_id: hash,
    instance_id: hash.nullable(),
    payload: payloadSchema.nullable(),
    radar: weatherManifestSchema.nullable(),
    grid: gridSchema.nullable(),
  })
  .superRefine((p, ctx) => {
    const reject = (message: string) =>
      ctx.addIssue({ code: 'custom', message });
    if (p.state === 'off' || p.state === 'unavailable') {
      if (
        [
          p.instance_id,
          p.payload,
          p.radar,
          p.grid,
          p.coverage,
          p.observed_at_ms,
          p.issued_at_ms,
          p.scan_start_ms,
          p.scan_end_ms,
          p.valid_at_ms,
          p.valid_from_ms,
          p.valid_to_ms,
          p.run_at_ms,
          p.lead_seconds,
          p.retrieved_at_ms,
          p.fresh_until_ms,
          p.expires_at_ms,
        ].some((v) => v !== null)
      )
        reject('Off/unavailable products cannot supply data');
      return;
    }
    if (
      p.instance_id === null ||
      p.coverage === null ||
      p.retrieved_at_ms === null ||
      p.fresh_until_ms === null ||
      p.expires_at_ms === null
    ) {
      reject('Incomplete instance');
      return;
    }
    if (
      !(
        p.retrieved_at_ms <= p.generated_at_ms &&
        p.generated_at_ms < p.expires_at_ms
      ) ||
      p.fresh_until_ms > p.expires_at_ms ||
      p.expires_at_ms > p.coverage.expires_at_ms ||
      (p.state === 'stale') !== p.generated_at_ms >= p.fresh_until_ms
    )
      reject('Incoherent deadlines/state');
    if (p.validity_kind === 'instant') {
      if (
        p.valid_at_ms === null ||
        p.valid_from_ms !== null ||
        p.valid_to_ms !== null
      )
        reject('Invalid instant');
    } else if (p.validity_kind === 'interval') {
      if (
        p.valid_at_ms !== null ||
        p.valid_from_ms === null ||
        p.valid_to_ms === null ||
        p.valid_from_ms >= p.valid_to_ms ||
        p.generated_at_ms >= p.valid_to_ms
      )
        reject('Invalid interval');
    } else if (
      [p.valid_at_ms, p.valid_from_ms, p.valid_to_ms].some((v) => v !== null) ||
      p.method_kind !== 'reported' ||
      !['station-v1', 'advisory-v1'].includes(p.representation)
    )
      reject('Invalid collection time');
    if (
      (p.scan_start_ms === null) !== (p.scan_end_ms === null) ||
      (p.scan_start_ms !== null &&
        p.scan_end_ms !== null &&
        p.scan_start_ms > p.scan_end_ms)
    )
      reject('Invalid scan');
    if (p.time_kind === 'observation') {
      if (
        !['reported', 'sensor', 'derived'].includes(p.method_kind) ||
        p.run_at_ms !== null ||
        p.lead_seconds !== null ||
        (p.observed_at_ms === null &&
          p.scan_end_ms === null &&
          p.validity_kind !== 'collection')
      )
        reject('Invalid observation');
      if (
        [p.observed_at_ms, p.scan_end_ms].some(
          (v) => v !== null && v > p.generated_at_ms + 60000
        )
      )
        reject('Future observation');
    } else {
      if (p.observed_at_ms !== null || p.scan_start_ms !== null)
        reject('Forecast/analysis is not a sensor observation');
      if (p.method_kind === 'numerical-model') {
        if (
          p.run_at_ms === null ||
          p.lead_seconds === null ||
          p.validity_kind !== 'instant' ||
          p.valid_at_ms !== p.run_at_ms + 1000 * p.lead_seconds ||
          (p.time_kind === 'analysis' && p.lead_seconds !== 0)
        )
          reject('Invalid model identity');
      } else if (
        p.time_kind !== 'forecast' ||
        p.method_kind !== 'reported' ||
        p.run_at_ms !== null ||
        p.lead_seconds !== null ||
        (p.issued_at_ms === null && p.validity_kind !== 'collection')
      )
        reject('Invalid reported forecast');
    }
    if (p.representation === 'xyz-rgba-pair-v1') {
      const r = p.radar;
      if (
        p.product_type !== 'observed-precipitation' ||
        !r ||
        r.state !== 'ready' ||
        p.payload !== null ||
        p.grid !== null ||
        p.coverage.mask_encoding !== 'absence-rgba-v1' ||
        p.product_id !== r.product_id ||
        p.source_id !== r.source ||
        p.observed_at_ms !== r.frame_time_ms ||
        p.coverage.generation !== String(r.coverage_token) ||
        p.coverage.expires_at_ms !== r.coverage_expires_at_ms
      )
        reject('Invalid radar compatibility binding');
    } else if (
      p.radar !== null ||
      !p.payload ||
      p.payload.path.split('/')[5] !== p.instance_id
    )
      reject('Invalid immutable payload identity');
    if (p.representation === 'latlon-grid-v1') {
      if (
        !p.grid ||
        p.coverage.mask_encoding !== 'uint8-validity-v1' ||
        p.payload?.content_type !== 'application/json'
      ) {
        reject('Grid requires geometry and mask');
      } else {
        const minimum =
          p.grid.width * p.grid.height * (2 * p.grid.components.length + 1);
        if (p.payload.decoded_bytes < minimum || p.payload.gpu_bytes < minimum)
          reject('Underdeclared grid allocations');
      }
    } else if (p.grid !== null) reject('Unexpected grid geometry');
    else if (
      p.representation !== 'xyz-rgba-pair-v1' &&
      (p.coverage.mask_encoding !== 'feature-collection-v1' ||
        p.payload?.content_type !== 'application/geo+json')
    )
      reject('Invalid geographic collection');
  });

const catalogSchema = z
  .strictObject({
    schema: z.literal('aviation-weather-v1'),
    generated_at_ms: integer,
    settings_revision: integer,
    products: z.array(weatherProductSchema).max(16),
  })
  .refine(
    (c) =>
      new Set(c.products.map((p) => p.layer_id)).size === c.products.length &&
      c.products.every((p) => p.generated_at_ms === c.generated_at_ms)
  );
const settingsSchema = z.strictObject({
  metar: z.boolean(),
  taf: z.boolean(),
  sigmet: z.boolean(),
  winds: z.boolean().default(false),
  temperature: z.boolean().default(false),
  gfs_selection: z
    .strictObject({
      pressure_pa: z.union([
        z.literal(85000),
        z.literal(50000),
        z.literal(30000),
        z.literal(25000),
        z.literal(20000),
      ]),
      horizon_hours: z.union([
        z.literal(0),
        z.literal(3),
        z.literal(6),
        z.literal(9),
        z.literal(12),
        z.literal(18),
        z.literal(24),
        z.literal(36),
        z.literal(48),
      ]),
    })
    .default({ pressure_pa: 50000, horizon_hours: 0 }),
  revision: integer,
});
export type AviationCatalog = z.infer<typeof catalogSchema>;
export type AviationProduct = z.infer<typeof weatherProductSchema>;
export type AviationSettings = z.input<typeof settingsSchema>;
export type AviationLayer = 'metar' | 'taf' | 'sigmet';
export const parseAviationCatalog = (data: unknown): AviationCatalog =>
  catalogSchema.parse(data);
export const parseAviationSettings = (data: unknown): AviationSettings =>
  settingsSchema.parse(data);
export const aviationWeatherApi = {
  async getSettings(signal?: AbortSignal) {
    const { data } = await apiClient.get<unknown>(
      '/api/aviation-weather/v1/settings',
      { signal }
    );
    return parseAviationSettings(data);
  },
  async updateSettings(
    changes: Partial<Pick<AviationSettings, AviationLayer>>
  ) {
    const { data } = await apiClient.put<unknown>(
      '/api/aviation-weather/v1/settings',
      changes
    );
    return parseAviationSettings(data);
  },
  async getCatalog(signal?: AbortSignal) {
    const { data } = await apiClient.get<unknown>(
      '/api/aviation-weather/v1/catalog',
      { signal }
    );
    return parseAviationCatalog(data);
  },
};
