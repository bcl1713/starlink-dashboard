import { describe, expect, it } from 'vitest';
import { parseAviationFeatures, activeFeatures } from './aviation-features';
import {
  NOW,
  station,
  advisory,
  collection,
} from '@/pages/aviation-weather/fixtures';
describe('normalized aviation features', () => {
  it('preserves SI values, unknowns, bounds and forecast groups', () => {
    const s = parseAviationFeatures(collection([station(true)]), 'taf')
      .features[0];
    expect(s.properties).toMatchObject({
      temperature_k: 280,
      gust_mps: null,
      visibility_lower_bound: true,
      ceiling_known: true,
      forecast_groups: [{ wind_speed_mps: 5 }],
    });
  });
  it('rejects provider fields, missing null semantics, unit confusion and invalid intervals', () => {
    for (const changes of [
      { wind_gust_mps: 5 },
      { ceiling_reference: 'MSL' },
      { valid_to_ms: NOW },
      { wind_direction_deg: 400 },
    ]) {
      const s = station(true);
      Object.assign(s.properties, changes);
      expect(() => parseAviationFeatures(collection([s]), 'taf')).toThrow();
    }
    const s = station(true);
    delete (
      s.properties.forecast_groups[0] as Partial<
        (typeof s.properties.forecast_groups)[0]
      >
    ).ceiling_known;
    expect(() => parseAviationFeatures(collection([s]), 'taf')).toThrow();
  });
  it('retains future forecasts but renders half-open validity only', () => {
    const c = parseAviationFeatures(collection([station(true)]), 'taf');
    expect(activeFeatures(c, 'taf', NOW - 1)).toHaveLength(0);
    expect(activeFeatures(c, 'taf', NOW)).toHaveLength(1);
    expect(activeFeatures(c, 'taf', NOW + 3600000)).toHaveLength(0);
    expect(c.features).toHaveLength(1);
  });
  it('preserves unlocated text and excludes future, cancelled and expired advisories', () => {
    const a = advisory();
    a.geometry = null as unknown as typeof a.geometry;
    const c = parseAviationFeatures(collection([a]), 'sigmet');
    expect(activeFeatures(c, 'sigmet', NOW)[0].geometry).toBeNull();
    expect(activeFeatures(c, 'sigmet', NOW - 1)).toHaveLength(0);
    expect(activeFeatures(c, 'sigmet', NOW + 3600000)).toHaveLength(0);
    a.properties.cancelled = true;
    expect(
      activeFeatures(
        parseAviationFeatures(collection([a]), 'sigmet'),
        'sigmet',
        NOW
      )
    ).toHaveLength(0);
  });
  it('rejects excessive counts, unclosed rings and unsplit seams', () => {
    expect(() =>
      parseAviationFeatures(collection(Array(5001).fill(station())), 'metar')
    ).toThrow();
    const a = advisory();
    a.geometry.coordinates[0][4] = [1, 0];
    expect(() => parseAviationFeatures(collection([a]), 'sigmet')).toThrow();
    a.geometry.coordinates[0] = [
      [179, 0],
      [-179, 0],
      [-179, 1],
      [179, 1],
      [179, 0],
    ];
    expect(() => parseAviationFeatures(collection([a]), 'sigmet')).toThrow();
  });
});

it('rejects ambiguous duplicate feature identities', () => {
  expect(() =>
    parseAviationFeatures(collection([station(), station()]), 'metar')
  ).toThrow();
});

it('uses the latest effective prevailing group and preserves uncertain BECMG alternatives', async () => {
  const { currentForecastGroups, prevailingForecast } = await import(
    './aviation-features'
  );
  const f = station(true);
  const first = f.properties.forecast_groups[0];
  f.properties.forecast_groups.push({
    ...first,
    change_type: 'BECMG' as never,
    time_becoming_ms: (NOW + 120000) as never,
    valid_from_ms: NOW + 60000,
    wind_speed_mps: 15,
  });
  const normalized = parseAviationFeatures(collection([f]), 'taf')
    .features[0] as import('./aviation-features').AviationStation;
  expect(prevailingForecast(normalized, NOW + 90000)?.wind_speed_mps).toBe(5);
  expect(currentForecastGroups(normalized, NOW + 90000)).toHaveLength(2);
  expect(prevailingForecast(normalized, NOW + 120000)?.wind_speed_mps).toBe(15);
  expect(currentForecastGroups(normalized, NOW + 120000)).toHaveLength(1);
});
