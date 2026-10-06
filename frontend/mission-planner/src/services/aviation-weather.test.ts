import { describe, expect, it } from 'vitest';
import fixture from '@/test/aviation-catalog.json';
import {
  parseAviationCatalog,
  parseAviationSettings,
} from './aviation-weather';

const copy = () => structuredClone(fixture);

describe('aviation catalog admission before acquisition', () => {
  it('retains observations and unknown coverage distinctly', () => {
    const catalog = parseAviationCatalog(fixture);
    expect(catalog.products[0].observed_at_ms).toBe(1791244200000);
    expect(catalog.products[0].coverage?.missing_meaning).toBe(
      'unknown-not-clear'
    );
  });
  it.each([
    { observed_at_ms: true },
    { time_kind: 'analysis' },
    { method_kind: 'numerical-model' },
    { run_at_ms: 1791244800000 },
    { observed_at_ms: 1791244860001 },
    { fresh_until_ms: 1791245400001 },
    { expires_at_ms: 1791244800000 },
    { instance_id: null },
    { representation: 'future-v2' },
    { state: 'off' },
    { extra: 0 },
  ])('rejects incoherent product %j', (change) => {
    const data = copy();
    Object.assign(data.products[0], change);
    expect(() => parseAviationCatalog(data)).toThrow();
  });
  it.each([
    'https://evil.test/data',
    '//evil.test/data',
    '/api/private/data',
    '/api/aviation-weather/v1/products/../data',
    '/api/aviation-weather/v1/products/%2e%2e/data',
    `/api/aviation-weather/v1/products/${'d'.repeat(64)}/stations.json`,
  ])('rejects an unsafe or mismatched path %s', (path) => {
    const data = copy();
    data.products[0].payload.path = path;
    expect(() => parseAviationCatalog(data)).toThrow();
  });
  it.each([
    ['encoded_bytes', 16 * 1024 ** 2],
    ['decoded_bytes', 32 * 1024 ** 2],
    ['gpu_bytes', 16 * 1024 ** 2],
  ] as const)('rejects excessive %s', (field, limit) => {
    const data = copy();
    data.products[0].payload[field] = limit + 1;
    expect(() => parseAviationCatalog(data)).toThrow();
  });
  it('rejects duplicate layers and future schemas', () => {
    const data = copy();
    data.products.push(data.products[0]);
    expect(() => parseAviationCatalog(data)).toThrow();
    expect(() =>
      parseAviationCatalog({ ...fixture, schema: 'future-v2' })
    ).toThrow();
  });
  it('requires coherent model run and pressure identity', () => {
    const data = copy();
    Object.assign(data.products[0], {
      time_kind: 'forecast',
      method_kind: 'numerical-model',
      observed_at_ms: null,
      run_at_ms: 1791241200000,
      lead_seconds: 7200,
      valid_at_ms: 1791248400000,
      vertical: { kind: 'pressure', pressure_pa: 50000 },
    });
    expect(parseAviationCatalog(data).products[0].time_kind).toBe('forecast');
    data.products[0].valid_at_ms = 1791244800000;
    expect(() => parseAviationCatalog(data)).toThrow();
  });
  it('accepts only strictly typed default-off settings', () => {
    expect(
      parseAviationSettings({
        metar: false,
        taf: false,
        sigmet: false,
        revision: 0,
      }).metar
    ).toBe(false);
    expect(() =>
      parseAviationSettings({
        metar: 1,
        taf: false,
        sigmet: false,
        revision: 0,
      })
    ).toThrow();
  });
});
