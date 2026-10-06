import { z } from 'zod';
import type { AviationLayer } from './aviation-weather';
const time = z.number().int().nonnegative().max(8640000000000000);
const value = z.number().finite().nonnegative().nullable();
const text = z.string().max(65536);
const optionalText = text.nullable();
const coordinate = z.tuple([
  z.number().finite().min(-180).max(180),
  z.number().finite().min(-90).max(90),
]);
const weather = {
  wind_direction_deg: z.number().finite().min(0).max(360).nullable(),
  wind_variable: z.boolean(),
  wind_speed_mps: value,
  gust_mps: value,
  visibility_m: value,
  visibility_lower_bound: z.boolean(),
  ceiling_m: value,
  ceiling_known: z.boolean(),
  weather_codes: z.array(z.string().max(256)).max(64),
};
const group = z
  .strictObject({
    change_type: optionalText,
    time_becoming_ms: time.nullable(),
    probability: z.number().int().min(0).max(100).nullable(),
    valid_from_ms: time,
    valid_to_ms: time,
    ...weather,
  })
  .refine(
    (p) =>
      p.valid_from_ms < p.valid_to_ms &&
      (p.time_becoming_ms === null ||
        (p.valid_from_ms <= p.time_becoming_ms &&
          p.time_becoming_ms <= p.valid_to_ms)) &&
      (!p.wind_variable || p.wind_direction_deg === null) &&
      (p.ceiling_known || p.ceiling_m === null)
  );
const stationProperties = z
  .strictObject({
    station_id: z.string().regex(/^[A-Za-z0-9_-]{1,64}$/),
    report_type: z.enum(['METAR', 'SPECI', 'TAF']),
    raw_text: text.min(1),
    observed_at_ms: time.nullable(),
    issued_at_ms: time.nullable(),
    valid_from_ms: time.nullable(),
    valid_to_ms: time.nullable(),
    ...weather,
    ceiling_reference: z.literal('AGL'),
    pressure_pa: value,
    temperature_k: value,
    dewpoint_k: value,
    flight_category: z.enum(['VFR', 'MVFR', 'IFR', 'LIFR']).nullable(),
    fresh_until_ms: time,
    expires_at_ms: time,
    forecast_groups: z.array(group).max(512),
  })
  .superRefine((p, ctx) => {
    const reject = () =>
      ctx.addIssue({
        code: 'custom',
        message: 'Incoherent station validity or weather',
      });
    if (
      p.fresh_until_ms > p.expires_at_ms ||
      (p.wind_variable && p.wind_direction_deg !== null) ||
      (!p.ceiling_known && p.ceiling_m !== null)
    )
      reject();
    if (p.report_type === 'TAF') {
      if (
        p.observed_at_ms !== null ||
        p.issued_at_ms === null ||
        p.valid_from_ms === null ||
        p.valid_to_ms === null ||
        p.valid_from_ms >= p.valid_to_ms ||
        p.expires_at_ms !== p.valid_to_ms ||
        !p.forecast_groups.length ||
        p.forecast_groups.some(
          (g) =>
            g.valid_from_ms < p.valid_from_ms! || g.valid_to_ms > p.valid_to_ms!
        )
      )
        reject();
    } else if (
      p.observed_at_ms === null ||
      p.issued_at_ms !== null ||
      p.valid_from_ms !== null ||
      p.valid_to_ms !== null ||
      p.forecast_groups.length ||
      p.observed_at_ms >= p.fresh_until_ms ||
      p.fresh_until_ms >= p.expires_at_ms
    )
      reject();
  });
const ring = z
  .array(coordinate)
  .min(4)
  .max(100000)
  .refine(
    (r) =>
      r[0][0] === r.at(-1)![0] &&
      r[0][1] === r.at(-1)![1] &&
      r.every((p, i) => !i || Math.abs(p[0] - r[i - 1][0]) <= 180),
    'Unclosed or unsplit polygon ring'
  );
const polygon = z.array(ring).min(1).max(100000);
const advisoryGeometry = z
  .union([
    z.strictObject({ type: z.literal('Polygon'), coordinates: polygon }),
    z.strictObject({
      type: z.literal('MultiPolygon'),
      coordinates: z.array(polygon).min(1).max(500),
    }),
  ])
  .nullable();
const vertical = z
  .strictObject({
    lower: value,
    upper: value,
    unit: z.enum(['m', 'flight-level', 'unknown']),
    reference: z.enum(['AGL', 'MSL', 'FL', 'unknown']),
  })
  .refine(
    (v) =>
      (v.lower === null || v.upper === null || v.lower <= v.upper) &&
      (v.unit === 'flight-level') === (v.reference === 'FL') &&
      (v.unit === 'unknown') === (v.reference === 'unknown') &&
      (v.unit !== 'unknown' || (v.lower === null && v.upper === null))
  );
const advisoryProperties = z
  .strictObject({
    issuer: optionalText,
    fir: optionalText,
    series: optionalText,
    bulletin_series: optionalText,
    cancellation_target: z
      .strictObject({
        series: text.min(1),
        valid_from_ms: time.nullable(),
        valid_to_ms: time.nullable(),
      })
      .refine(
        (p) =>
          (p.valid_from_ms === null && p.valid_to_ms === null) ||
          (p.valid_from_ms !== null &&
            p.valid_to_ms !== null &&
            p.valid_from_ms < p.valid_to_ms)
      )
      .nullable(),
    revision: optionalText,
    phenomenon: optionalText,
    severity: optionalText,
    raw_text: text.min(1),
    issued_at_ms: time.nullable(),
    valid_from_ms: time,
    valid_to_ms: time,
    vertical,
    cancelled: z.boolean(),
    amends: optionalText,
    expires_at_ms: time,
  })
  .refine(
    (p) => p.valid_from_ms < p.valid_to_ms && p.expires_at_ms === p.valid_to_ms
  );
const stationSchema = z.strictObject({
  type: z.literal('Feature'),
  id: z.string().min(1).max(256),
  geometry: z.strictObject({
    type: z.literal('Point'),
    coordinates: coordinate,
  }),
  properties: stationProperties,
});
const advisorySchema = z.strictObject({
  type: z.literal('Feature'),
  id: z.string().min(1).max(256),
  geometry: advisoryGeometry,
  properties: advisoryProperties,
});
const metadata = {
  type: z.literal('FeatureCollection'),
  source_id: z.literal('awc'),
  retrieved_at_ms: time,
  feed_completeness: z.enum(['unknown', 'partial']),
  omitted_features: z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER),
};
const stations = z.strictObject({
  ...metadata,
  features: z.array(stationSchema).max(5000),
});
const advisories = z.strictObject({
  ...metadata,
  features: z.array(advisorySchema).max(500),
});
export type AviationStation = z.infer<typeof stationSchema>;
export type AviationAdvisory = z.infer<typeof advisorySchema>;
export type AviationFeature = AviationStation | AviationAdvisory;
export type AviationCollection = Omit<z.infer<typeof stations>, 'features'> & {
  features: AviationFeature[];
};
export function parseAviationFeatures(
  data: unknown,
  layer: AviationLayer
): AviationCollection {
  if (layer !== 'sigmet') {
    const c = stations.parse(data);
    if (
      new Set(c.features.map((f) => f.id)).size !== c.features.length ||
      new Set(c.features.map((f) => f.properties.station_id)).size !==
        c.features.length
    )
      throw Error('Duplicate station identity');
    if (
      c.features.some(
        (f) => (f.properties.report_type === 'TAF') !== (layer === 'taf')
      )
    )
      throw Error('Incorrect station report type');
    return c;
  }
  const c = advisories.parse(data);
  if (new Set(c.features.map((f) => f.id)).size !== c.features.length)
    throw Error('Duplicate advisory identity');
  let vertices = 0,
    polygons = 0;
  for (const f of c.features)
    if (f.geometry) {
      const parts =
        f.geometry.type === 'Polygon'
          ? [f.geometry.coordinates]
          : f.geometry.coordinates;
      polygons += parts.length;
      for (const p of parts) for (const r of p) vertices += r.length;
    }
  if (vertices > 100000 || polygons > 500)
    throw Error('Advisory geometry budget');
  return c;
}
export function activeFeatures(
  c: AviationCollection,
  layer: AviationLayer,
  now: number
): AviationFeature[] {
  return c.features.filter((f) => {
    const p = f.properties;
    if (now >= p.expires_at_ms) return false;
    if ('station_id' in p && layer === 'metar') return true;
    return (
      p.valid_from_ms !== null &&
      p.valid_to_ms !== null &&
      p.valid_from_ms <= now &&
      now < p.valid_to_ms &&
      (!('cancelled' in p) || !p.cancelled)
    );
  });
}
export function currentForecastGroups(f: AviationStation, now: number) {
  const p = f.properties;
  if (
    p.valid_from_ms === null ||
    p.valid_to_ms === null ||
    now < p.valid_from_ms ||
    now >= p.valid_to_ms
  )
    return [];
  const active = p.forecast_groups.filter(
    (g) => g.valid_from_ms <= now && now < g.valid_to_ms
  );
  const established = active.filter(
    (g) =>
      g.probability === null &&
      (g.change_type === null ||
        g.change_type === 'FM' ||
        (g.change_type === 'BECMG' &&
          g.time_becoming_ms !== null &&
          now >= g.time_becoming_ms))
  );
  established.sort(
    (a, b) =>
      (b.change_type === 'BECMG' ? b.time_becoming_ms! : b.valid_from_ms) -
      (a.change_type === 'BECMG' ? a.time_becoming_ms! : a.valid_from_ms)
  );
  const alternatives = active.filter((g) => !established.includes(g));
  return [...established.slice(0, 1), ...alternatives];
}
export function prevailingForecast(f: AviationStation, now: number) {
  return currentForecastGroups(f, now).find(
    (g) =>
      g.probability === null &&
      (g.change_type === null ||
        g.change_type === 'FM' ||
        (g.change_type === 'BECMG' &&
          g.time_becoming_ms !== null &&
          now >= g.time_becoming_ms))
  );
}
// Only a known combination determines a category. Lower-bound visibility can
// span multiple categories; preserve that uncertainty instead of assigning VFR.
export function forecastCategory(
  g: z.infer<typeof group>
): AviationStation['properties']['flight_category'] {
  const vr = (v: number) =>
    v < 1609.344 ? 3 : v < 4828.032 ? 2 : v <= 8046.72 ? 1 : 0;
  const vis =
    g.visibility_m === null
      ? [0, 1, 2, 3]
      : g.visibility_lower_bound
        ? Array.from({ length: vr(g.visibility_m) + 1 }, (_, i) => i)
        : [vr(g.visibility_m)];
  const sky = !g.ceiling_known
    ? [0, 1, 2, 3]
    : g.ceiling_m === null
      ? [0]
      : [
          g.ceiling_m < 152.4
            ? 3
            : g.ceiling_m < 304.8
              ? 2
              : g.ceiling_m <= 914.4
                ? 1
                : 0,
        ];
  const possibilities = new Set(
    vis.flatMap((v) => sky.map((s) => Math.max(v, s)))
  );
  return possibilities.size === 1
    ? (['VFR', 'MVFR', 'IFR', 'LIFR'] as const)[[...possibilities][0]]
    : null;
}
