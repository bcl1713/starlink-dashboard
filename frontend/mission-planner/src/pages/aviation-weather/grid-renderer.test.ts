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
it.each(['winds', 'temperature'] as const)(
  'owns and releases exact %s raster allocations',
  (mode) => {
    const l = lease(),
      budget = new WeatherBudget();
    l.u[0] = -32768;
    l.v[0] = 32767;
    l.mask[0] = 3;
    const d = createGridDrawing(
      l,
      { winds: mode === 'winds', temperature: mode === 'temperature' },
      budget
    );
    const raster = d.object.getObjectByName(
      mode === 'winds' ? 'GFS wind speed' : 'GFS temperature'
    ) as THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
    expect(raster).toBeTruthy();
    const texture = raster.material.uniforms[
      mode === 'winds' ? 'packedU' : 'packedGrid'
    ].value as THREE.DataTexture;
    expect(Array.from((texture.image.data as Uint8Array).slice(0, 4))).toEqual(
      mode === 'winds' ? [0, 128, 3, 255] : [24, 252, 3, 255]
    );
    if (mode === 'winds') {
      const v = raster.material.uniforms.packedV.value as THREE.DataTexture;
      expect(Array.from((v.image.data as Uint8Array).slice(0, 4))).toEqual([
        255, 127, 3, 255,
      ]);
      expect(d.object.getObjectByName('GFS temperature')).toBeUndefined();
    }
    expect(texture.minFilter).toBe(THREE.NearestFilter);
    expect(texture.generateMipmaps).toBe(false);
    expect(raster.renderOrder).toBeLessThan(-100);
    expect(raster.material.depthWrite).toBe(false);
    expect(raster.material.toneMapped).toBe(false);
    expect(d.bytes.gpu).toBeLessThanOrEqual(4 * 1024 ** 2);
    expect(budget.snapshot().gpu).toBe(d.bytes.gpu);
    expect(budget.snapshot().decoded).toBe(d.bytes.decoded);
    expect(d.object.getObjectByName('GFS wind FROM barbs')).toBeUndefined();
    d.dispose();
    d.dispose();
    expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
    expect(texture.image.data?.byteLength).toBe(0);
  }
);
it('resolves a direct legacy both-layer request to wind only', () => {
  const d = createGridDrawing(
    lease(),
    { winds: true, temperature: true },
    new WeatherBudget()
  );
  expect(d.mode).toBe('winds');
  expect(d.object.getObjectByName('GFS wind speed')).toBeTruthy();
  expect(d.object.getObjectByName('GFS temperature')).toBeUndefined();
  d.dispose();
});
it('rejects before native allocation when the combined allowance is full', () => {
  const budget = new WeatherBudget();
  const hold = budget.reserve('other', {
    encoded: 0,
    decoded: 0,
    gpu: 16 * 1024 ** 2,
  });
  expect(() =>
    createGridDrawing(lease(), { winds: true, temperature: false }, budget)
  ).toThrow();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 16 * 1024 ** 2 });
  hold.release();
});
it('returns an empty owned drawing for off mode', () => {
  const budget = new WeatherBudget();
  const d = createGridDrawing(
    lease(),
    { winds: false, temperature: false },
    budget
  );
  expect(d.mode).toBe('off');
  expect(d.object.children).toHaveLength(0);
  d.dispose();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
it('renders only the outward-facing atmospheric surface and has coherent triangle winding', () => {
  const d = createGridDrawing(
    lease(),
    { winds: false, temperature: true },
    new WeatherBudget()
  );
  const mesh = d.object.getObjectByName('GFS temperature') as THREE.Mesh<
    THREE.BufferGeometry,
    THREE.ShaderMaterial
  >;
  const positions = mesh.geometry.getAttribute('position');
  const a = new THREE.Vector3(),
    b = new THREE.Vector3(),
    c = new THREE.Vector3();
  for (let i = 0; i < positions.count; i += 3) {
    a.fromBufferAttribute(positions, i);
    b.fromBufferAttribute(positions, i + 1);
    c.fromBufferAttribute(positions, i + 2);
    expect(b.sub(a).cross(c.sub(a)).dot(a)).toBeGreaterThan(0);
  }
  expect(mesh.material.side).toBe(THREE.FrontSide);
  d.dispose();
});
