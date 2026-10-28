import { expect, it } from 'vitest';
import * as THREE from 'three';
import {
  DEFAULT_EMISSION,
  resolveCityEmission,
  updateCityEmissionUniforms,
} from '../../pages/overview-bloom-mode';
import { tuningReport } from './tuning-report';
import { DEFAULT_BLOOM } from './contracts';

it('keeps baseline city emission fixed and uses warm configurable HDR only in B', () => {
  const baseline = resolveCityEmission(false, {
    ...DEFAULT_EMISSION,
    cities: 80,
    cityColor: '#ff0000',
  });
  expect(baseline.intensity).toBe(0.35);
  expect(baseline.color.toArray()).toEqual([0.92, 0.96, 1]);
  const warm = resolveCityEmission(true, DEFAULT_EMISSION);
  expect(warm.intensity).toBe(DEFAULT_EMISSION.cities);
  expect(warm.color.r).toBeGreaterThan(warm.color.g);
  expect(warm.color.g).toBeGreaterThan(warm.color.b);
  const uniforms = {
    cityEmissionIntensity: { value: 0 },
    citySurfaceScale: { value: 1 },
    cityEmissionColor: { value: new THREE.Color() },
  };
  const sameColor = uniforms.cityEmissionColor.value;
  updateCityEmissionUniforms(uniforms, true, {
    ...DEFAULT_EMISSION,
    cities: 36,
    cityColor: '#ffaa33',
  });
  expect(uniforms.cityEmissionIntensity.value).toBe(36);
  expect(uniforms.cityEmissionColor.value).toBe(sameColor);
  expect(sameColor.getHexString()).toBe('ffaa33');
});
it('exports current tuning without timing runs and takes an independent snapshot', () => {
  const emissions = { ...DEFAULT_EMISSION, cities: 36, lines: 2.5 };
  const input = {
    sourceSha: 'abc123',
    sourceDirty: false,
    mode: 'bloom' as const,
    settings: { ...DEFAULT_BLOOM },
    emissions,
    isolateCities: true,
    scene: { full: false, path: false, paused: true, epoch: 2 },
    frame: { camera: [0, 2, 6.8], dpr: 2, dimensions: { bright: [480, 240] } },
    power: 'Laptop AC',
  };
  const text = JSON.stringify(tuningReport(input));
  emissions.cities = 0;
  const value = JSON.parse(text);
  expect(value.schema).toBe('overview-bloom-tuning/v1');
  expect(value.emissions.cities).toBe(36);
  expect(value.emissions.lines).toBe(2.5);
  expect(value.sourceSha).toBe('abc123');
  expect(value.isolateCities).toBe(true);
  expect(value.frame.camera).toEqual([0, 2, 6.8]);
  expect(value.frame.dimensions.bright).toEqual([480, 240]);
  expect(value.cityEmission.colorLinear[0]).toBeGreaterThan(
    value.cityEmission.colorLinear[2]
  );
});
