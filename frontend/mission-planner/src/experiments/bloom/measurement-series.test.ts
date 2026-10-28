import { expect, it } from 'vitest';
import { measurementSeries } from './measurement-series';
import { DEFAULT_BLOOM } from './contracts';
import { DEFAULT_EMISSION } from '../../pages/overview-bloom-mode';
it.each(['bright', 'bloom'] as const)(
  'measures final scene even when starting from %s debug view',
  (view) => {
    const base = {
      settings: { ...DEFAULT_BLOOM, view, exposure: 1.7 },
      emissions: { ...DEFAULT_EMISSION, cities: 36 },
      full: true,
      path: true,
      power: 'AC',
      sampleFrames: 60,
    };
    const runs = measurementSeries(base, true);
    expect(runs.map((r) => r.mode)).toEqual(['output', 'bloom', 'bloom']);
    expect(runs.map((r) => r.settings.maxDimension)).toEqual([960, 480, 1920]);
    expect(runs.every((r) => r.settings.view === 'final')).toBe(true);
    expect(
      runs.every(
        (r) => r.settings.exposure === 1.7 && r.emissions.cities === 36
      )
    ).toBe(true);
    expect(base.settings.view).toBe(view);
  }
);
