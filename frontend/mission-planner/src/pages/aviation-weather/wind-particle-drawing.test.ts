import { expect, it } from 'vitest';
import * as THREE from 'three';
import { lease } from '@/test/gfs-lease';
import { WeatherBudget } from './weather-budget';
import { createGridDrawing } from './grid-renderer';

it('owns bounded depth-tested trails and releases their reservations once', async () => {
  const path = './wind-particle-drawing';
  const { createWindParticleDrawing } = (await import(
    path
  )) as typeof import('./wind-particle-drawing');
  const budget = new WeatherBudget(),
    d = createWindParticleDrawing(lease(), budget);
  expect(d.object.name).toBe('GFS wind particles');
  const lines = d.object as THREE.LineSegments<
    THREE.BufferGeometry,
    THREE.ShaderMaterial
  >;
  expect(lines.material.depthTest).toBe(true);
  expect(lines.material.depthWrite).toBe(false);
  expect(lines.renderOrder).toBeLessThan(0);
  const hits: THREE.Intersection[] = [];
  lines.raycast(new THREE.Raycaster(), hits);
  expect(hits).toEqual([]);
  expect(lines.geometry.getAttribute('position').count).toBe(2000 * 11 * 2);
  expect(budget.snapshot().gpu).toBe(d.bytes.gpu);
  d.update(1 / 30);
  expect(lines.geometry.drawRange.count).toBeGreaterThan(0);
  const state = lines.userData.windParticles;
  d.dispose();
  d.dispose();
  d.update(1);
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
  expect(state.grid).toBeUndefined();
  expect(state.positions.length).toBe(0);
});
it('only creates particles for wind and releases/recreates them on reduced motion', () => {
  const budget = new WeatherBudget(),
    l = lease();
  const d = createGridDrawing(l, { winds: true, temperature: false }, budget, {
    reducedMotion: true,
  });
  const rasterBytes = { ...d.bytes };
  expect(typeof d.setReducedMotion).toBe('function');
  expect(d.object.getObjectByName('GFS wind particles')).toBeUndefined();
  d.setReducedMotion(false);
  expect(d.object.getObjectByName('GFS wind particles')).toBeTruthy();
  expect(d.bytes.gpu).toBeGreaterThan(rasterBytes.gpu);
  expect(d.bytes.gpu).toBeLessThanOrEqual(4 * 1024 ** 2);
  d.setReducedMotion(true);
  expect(d.object.getObjectByName('GFS wind particles')).toBeUndefined();
  expect(d.bytes).toEqual(rasterBytes);
  d.dispose();
  d.setReducedMotion(false);
  expect(budget.snapshot().gpu).toBe(0);
  const temperature = createGridDrawing(
    l,
    { winds: false, temperature: true },
    budget
  );
  temperature.setReducedMotion(false);
  temperature.update(0.05);
  expect(
    temperature.object.getObjectByName('GFS wind particles')
  ).toBeUndefined();
  temperature.dispose();
});
it('rolls back the complete candidate when only the raster fits', () => {
  const budget = new WeatherBudget();
  const hold = budget.reserve('other', {
    encoded: 0,
    decoded: 0,
    gpu: 16 * 1024 ** 2 - 3500000,
  });
  expect(() =>
    createGridDrawing(lease(), { winds: true, temperature: false }, budget)
  ).toThrow();
  expect(budget.snapshot()).toMatchObject({
    decoded: 0,
    gpu: 16 * 1024 ** 2 - 3500000,
  });
  hold.release();
});
it('starts a replacement generation with empty trails and releases the previous field', () => {
  const budget = new WeatherBudget();
  const first = createGridDrawing(
    lease(),
    { winds: true, temperature: false },
    budget
  );
  first.update(1 / 30);
  const old =
    first.object.getObjectByName('GFS wind particles')!.userData.windParticles;
  expect(old.vertexCount).toBeGreaterThan(0);
  first.dispose();
  const next = lease();
  next.descriptor = { ...next.descriptor, instance_id: 'b'.repeat(64) };
  const second = createGridDrawing(
    next,
    { winds: true, temperature: false },
    budget
  );
  const state =
    second.object.getObjectByName('GFS wind particles')!.userData.windParticles;
  expect(state.instanceId).toBe('b'.repeat(64));
  expect(state.vertexCount).toBe(0);
  expect(state.alpha.every((n: number) => n === 0)).toBe(true);
  expect(old.grid).toBeUndefined();
  second.dispose();
  expect(budget.snapshot()).toMatchObject({ decoded: 0, gpu: 0 });
});
