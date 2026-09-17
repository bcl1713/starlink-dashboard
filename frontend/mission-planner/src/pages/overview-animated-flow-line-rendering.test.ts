import { describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import {
  FlowParticlePool,
  createAnimatedFlowResources,
  disposeAnimatedFlowResources,
  interpolateFlowPath,
  prepareFlowPath,
  writeFlowParticles,
} from './overview-animated-flow-line-rendering';

const points: [number, number, number][] = [
  [0, 0, 0],
  [2, 0, 0],
  [2, 2, 0],
];

const forward = {
  enabled: true,
  rate: 2,
  speed: 1,
  color: '#ffb000',
  size: 8,
  brightness: 1,
  maxParticles: 2,
  maxWorldSize: 0.05,
} as const;

describe('AnimatedFlowLine rendering contract', () => {
  it('prepares and interpolates arbitrary multi-segment paths', () => {
    const path = prepareFlowPath(points);

    expect(path.totalLength).toBe(4);
    expect(Array.from(path.cumulativeLengths)).toEqual([0, 2, 4]);
    expect(interpolateFlowPath(points, 0)).toEqual([0, 0, 0]);
    expect(interpolateFlowPath(points, 0.5)).toEqual([2, 0, 0]);
    expect(interpolateFlowPath(points, 1)).toEqual([2, 2, 0]);
    expect(interpolateFlowPath([], 0.5)).toBeNull();
    expect(interpolateFlowPath([[1, 2, 3]], 0.5)).toEqual([1, 2, 3]);
  });

  it('emits only at the whole-path start and traverses across segment boundaries', () => {
    const pool = new FlowParticlePool({
      forward: {
        ...forward,
        rate: 1,
        speed: 0.25,
        maxParticles: 4,
      },
      random: () => 0.5,
    });
    const resources = createAnimatedFlowResources(4);
    const path = prepareFlowPath(points);

    pool.update(1);
    expect(pool.snapshot().map((particle) => particle.progress)).toEqual([0]);
    writeFlowParticles(resources, path, pool.snapshot());
    const positions = resources.geometry.getAttribute(
      'position'
    ) as THREE.BufferAttribute;
    expect(positions.getX(0)).toBe(0);
    expect(positions.getY(0)).toBe(0);

    pool.update(1);
    expect(pool.snapshot().map((particle) => particle.progress)).toEqual([
      0.25,
      0,
    ]);
    writeFlowParticles(resources, path, pool.snapshot());
    expect(positions.getX(0)).toBeCloseTo(1);
    expect(positions.getY(0)).toBeCloseTo(0);
    expect(positions.getX(1)).toBe(0);
    expect(positions.getY(1)).toBe(0);

    disposeAnimatedFlowResources(resources);
  });

  it('uses one screen-space renderer-native Points resource with a world-size cap', () => {
    const resources = createAnimatedFlowResources(5);

    expect(resources.points).toBeInstanceOf(THREE.Points);
    expect(
      (resources.geometry.getAttribute('position') as THREE.BufferAttribute)
        .usage
    ).toBe(THREE.DynamicDrawUsage);
    expect(
      (resources.geometry.getAttribute('color') as THREE.BufferAttribute).usage
    ).toBe(THREE.DynamicDrawUsage);
    expect(
      (resources.geometry.getAttribute('maxWorldSize') as THREE.BufferAttribute)
        .usage
    ).toBe(THREE.DynamicDrawUsage);
    expect(resources.material.uniforms.uPixelRatio.value).toBe(1);
    expect(resources.material.uniforms.uViewportHeightPixels.value).toBe(1);
    expect(resources.material.uniforms.uDepthBias.value).toBeGreaterThan(0);
    expect(resources.material.blending).toBe(THREE.AdditiveBlending);
    expect(resources.material.toneMapped).toBe(false);
    expect(resources.points.frustumCulled).toBe(false);
    expect(resources.points.children).toHaveLength(0);
    expect(resources.points.castShadow).toBe(false);
    expect(resources.points.receiveShadow).toBe(false);

    disposeAnimatedFlowResources(resources);
  });

  it('orders forward and reverse particles independently within a bounded pool', () => {
    const pool = new FlowParticlePool({
      forward,
      reverse: { ...forward, color: '#00ffff', maxParticles: 1 },
      random: () => 0.5,
    });

    pool.update(0.5);
    const particles = pool.snapshot();

    expect(particles).toHaveLength(2);
    expect(particles.map((particle) => particle.direction)).toEqual([
      'forward',
      'reverse',
    ]);
    expect(particles[0].progress).toBeLessThan(particles[1].progress);
    pool.update(10);
    expect(pool.snapshot().length).toBeLessThanOrEqual(3);
  });

  it('snapshots emitter properties at birth while applying updates to new particles', () => {
    const pool = new FlowParticlePool({ forward, random: () => 0.5 });

    pool.update(0.5);
    pool.configure({
      ...forward,
      color: '#00ff00',
      speed: 2,
      maxWorldSize: 0.1,
    });
    pool.update(0.5);

    expect(pool.snapshot()[0]).toMatchObject({
      color: '#ffb000',
      speed: 1,
      maxWorldSize: 0.05,
    });
    expect(pool.snapshot()[1]).toMatchObject({
      color: '#00ff00',
      speed: 2,
      maxWorldSize: 0.1,
    });
  });

  it('keeps a failed particle in place as one expanding terminal flash', () => {
    const pool = new FlowParticlePool({
      forward: {
        ...forward,
        rate: 1,
        maxParticles: 1,
        failure: { probability: 1, duration: 0.5, color: '#ff304f' },
      },
      random: () => 0,
    });
    const resources = createAnimatedFlowResources(1);
    const path = prepareFlowPath(points);

    pool.update(1);
    pool.update(0.5);
    const burst = pool.snapshot()[0];
    expect(burst).toMatchObject({ state: 'burst', failureColor: '#ff304f' });

    writeFlowParticles(resources, path, [burst]);
    expect(resources.geometry.drawRange.count).toBe(1);
    expect(
      (resources.geometry.getAttribute('size') as THREE.BufferAttribute).getX(0)
    ).toBeGreaterThan(forward.size);
    expect(
      (
        resources.geometry.getAttribute('maxWorldSize') as THREE.BufferAttribute
      ).getX(0)
    ).toBeGreaterThan(forward.maxWorldSize);
    expect(
      (
        resources.geometry.getAttribute('brightness') as THREE.BufferAttribute
      ).getX(0)
    ).toBeGreaterThan(forward.brightness);

    disposeAnimatedFlowResources(resources);
  });

  it('retains in-flight particles while the rendered path geometry moves', () => {
    const pool = new FlowParticlePool({ forward, random: () => 0.5 });
    const resources = createAnimatedFlowResources(2);

    pool.update(0.5);
    const emitted = pool.snapshot()[0];
    const movedPath = prepareFlowPath([
      [10, 0, 0],
      [12, 0, 0],
      [12, 2, 0],
    ]);

    writeFlowParticles(resources, movedPath, pool.snapshot());

    expect(pool.snapshot()[0]).toBe(emitted);
    expect(
      (resources.geometry.getAttribute('position') as THREE.BufferAttribute).getX(
        0
      )
    ).toBeGreaterThanOrEqual(10);
    disposeAnimatedFlowResources(resources);
  });

  it('reuses a released particle slot rather than growing a new object pool', () => {
    const pool = new FlowParticlePool({
      forward: { ...forward, rate: 1, maxParticles: 1, speed: 2 },
      random: () => 0.5,
    });

    pool.update(1);
    const first = pool.snapshot()[0];
    pool.update(1);

    expect(pool.snapshot()[0]).toBe(first);
  });

  it('disposes the single geometry and material on cleanup', () => {
    const resources = createAnimatedFlowResources(2);
    const disposeGeometry = vi.spyOn(resources.geometry, 'dispose');
    const disposeMaterial = vi.spyOn(resources.material, 'dispose');

    disposeAnimatedFlowResources(resources);

    expect(disposeGeometry).toHaveBeenCalledOnce();
    expect(disposeMaterial).toHaveBeenCalledOnce();
  });
});
