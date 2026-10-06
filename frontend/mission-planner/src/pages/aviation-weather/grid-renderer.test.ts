import { expect, it } from 'vitest';
import * as THREE from 'three';
import { lease } from '@/test/gfs-lease';
import { WeatherBudget } from './weather-budget';
import { sampleGrid } from './grid-sampling';
import { createGridDrawing, earthPoint } from './grid-renderer';
it('maps geographic axes and conservatively interpolates signed physical components across seam and poles', () => {
  expect(earthPoint(0, 0, 1).toArray()).toEqual([1, 0, -0]);
  expect(earthPoint(90, 0, 1).y).toBe(1);
  expect(earthPoint(0, 90, 1).z).toBe(-1);
  const l = lease();
  l.u[719] = 100;
  l.u[0] = -100;
  l.mask[1] = 3;
  expect(sampleGrid(l, 90, 179.75).u).toBeCloseTo(0);
  expect(sampleGrid(l, 90, -180)).toEqual({ u: -1, v: 3, t: 263.15, mask: 0 });
  expect(sampleGrid(l, 90, -179.75)).toEqual({
    u: null,
    v: null,
    t: null,
    mask: 3,
  });
  expect(sampleGrid(l, -90, 180).mask).toBe(0);
  expect(sampleGrid(l, 91, 0).mask).toBe(1);
});
it('owns exact native allocations, packs signed values and masks without filtered categorical textures, and disposes once', () => {
  const l = lease(),
    budget = new WeatherBudget(),
    d = createGridDrawing(l, { winds: true, temperature: true }, budget);
  const raster = d.object.getObjectByName('GFS temperature') as THREE.Mesh<
    THREE.BufferGeometry,
    THREE.ShaderMaterial
  >;
  const texture = raster.material.uniforms.packedGrid
    .value as THREE.DataTexture;
  expect(Array.from((texture.image.data as Uint8Array).slice(0, 4))).toEqual([
    24, 252, 0, 255,
  ]);
  expect(texture.minFilter).toBe(THREE.NearestFilter);
  expect(texture.generateMipmaps).toBe(false);
  expect(raster.renderOrder).toBeLessThan(-100);
  expect(raster.material.depthWrite).toBe(false);
  expect(d.bytes.gpu).toBeLessThanOrEqual(4 * 1024 ** 2);
  expect(budget.snapshot().gpu).toBe(d.bytes.gpu);
  expect(budget.snapshot().decoded).toBe(d.bytes.decoded);
  expect(d.object.getObjectByName('GFS wind FROM barbs')).toBeTruthy();
  d.dispose();
  d.dispose();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
it('rejects before any native allocation when the combined weather allowance is full', () => {
  const budget = new WeatherBudget();
  const hold = budget.reserve('other', {
    encoded: 0,
    decoded: 0,
    gpu: 16 * 1024 ** 2,
  });
  expect(() =>
    createGridDrawing(lease(), { winds: true, temperature: true }, budget)
  ).toThrow();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 16 * 1024 ** 2 });
  hold.release();
});

it('represents every maximum-range wind pennant within the native allowance', () => {
  const l = lease();
  l.u.fill(-32768);
  l.v.fill(32767);
  const budget = new WeatherBudget();
  const d = createGridDrawing(l, { winds: true, temperature: true }, budget);
  expect(d.barbCount).toBe(2000);
  expect(d.bytes.gpu).toBeLessThanOrEqual(4 * 1024 ** 2);
  const flags = d.object.getObjectByName('GFS 50 kt pennants') as THREE.Mesh;
  expect(flags.geometry.getAttribute('position').count).toBe(2000 * 18 * 3);
  d.dispose();
});
