/** @vitest-environment jsdom */
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { WeatherTextureOwner } from './weather-textures';
import type { WeatherAtlasPair } from './weather-atlas';
function pair(coverage = document.createElement('canvas')): WeatherAtlasPair {
  const radar = document.createElement('canvas');
  radar.width = radar.height = coverage.width = coverage.height = 2048;
  return {
    radar,
    coverage,
    frameTimeMs: 1,
    coverageToken: 1,
    coverageExpiresAtMs: 2,
    dispose: vi.fn(),
  };
}
it('reuses coverage, disposes superseded GPU images, and borrows CPU canvases', () => {
  const owner = new WeatherTextureOwner();
  const first = pair();
  const a = owner.replace(first)!;
  expect(a.radar.generateMipmaps).toBe(false);
  expect(a.coverage.generateMipmaps).toBe(false);
  expect(a.radar.flipY).toBe(false);
  expect(a.radar.colorSpace).toBe(THREE.SRGBColorSpace);
  expect(a.coverage.colorSpace).toBe(THREE.NoColorSpace);
  const radarDispose = vi.spyOn(a.radar, 'dispose');
  const coverageDispose = vi.spyOn(a.coverage, 'dispose');
  const b = owner.replace(pair(first.coverage))!;
  expect(b.coverage).toBe(a.coverage);
  expect(radarDispose).toHaveBeenCalledTimes(1);
  expect(coverageDispose).not.toHaveBeenCalled();
  owner.replace(null);
  owner.dispose();
  expect(coverageDispose).toHaveBeenCalledTimes(1);
  expect(first.coverage.width).toBe(2048);
  expect(first.dispose).not.toHaveBeenCalled();
});
