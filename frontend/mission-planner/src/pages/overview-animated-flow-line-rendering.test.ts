import { describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import {
  FlowParticlePool,
  FlowParticlePoolLifecycle,
  createAnimatedFlowResources,
  disposeAnimatedFlowResources,
  interpolateFlowPath,
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
} as const;

describe('AnimatedFlowLine rendering contract', () => {
  it('interpolates arbitrary multi-segment paths including endpoints', () => {
    expect(interpolateFlowPath(points, 0)).toEqual([0, 0, 0]);
    expect(interpolateFlowPath(points, 0.5)).toEqual([2, 0, 0]);
    expect(interpolateFlowPath(points, 1)).toEqual([2, 2, 0]);
    expect(interpolateFlowPath([], 0.5)).toBeNull();
    expect(interpolateFlowPath([[1, 2, 3]], 0.5)).toEqual([1, 2, 3]);
  });

  it('uses one renderer-native Points resource with dynamic attributes', () => {
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
      (resources.geometry.getAttribute('size') as THREE.BufferAttribute).usage
    ).toBe(THREE.DynamicDrawUsage);
    expect(
      (resources.geometry.getAttribute('brightness') as THREE.BufferAttribute)
        .usage
    ).toBe(THREE.DynamicDrawUsage);
    expect(resources.points.children).toHaveLength(0);
    expect(resources.points.castShadow).toBe(false);
    expect(resources.points.receiveShadow).toBe(false);

    disposeAnimatedFlowResources(resources);
  });

  it('orders forward and reverse particles independently within a bounded pool', () => {
    const pool = new FlowParticlePool({
      points,
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
    const pool = new FlowParticlePool({ points, forward, random: () => 0.5 });

    pool.update(0.5);
    pool.configure({ ...forward, color: '#00ff00', speed: 2 });
    pool.update(0.5);

    expect(pool.snapshot()[0]).toMatchObject({ color: '#ffb000', speed: 1 });
    expect(pool.snapshot()[1]).toMatchObject({ color: '#00ff00', speed: 2 });
  });

  it('recycles deterministically and renders a bounded failure burst inside the path', () => {
    const pool = new FlowParticlePool({
      points,
      forward: {
        ...forward,
        rate: 1,
        maxParticles: 1,
        failure: { probability: 1, burstCount: 3, duration: 0.5 },
      },
      random: () => 0,
    });

    pool.update(1);
    pool.update(0.5);
    expect(pool.snapshot().some((particle) => particle.state === 'burst')).toBe(
      true
    );
    expect(pool.snapshot().every((particle) => particle.progress < 1)).toBe(
      true
    );
    expect(pool.snapshot().length).toBeLessThanOrEqual(3);
  });

  it('snapshots a configured failure color at birth and writes it for terminal bursts', () => {
    const pool = new FlowParticlePool({
      points,
      forward: {
        ...forward,
        rate: 1,
        maxParticles: 1,
        failure: {
          probability: 1,
          burstCount: 1,
          duration: 1,
          color: '#ff0000',
        },
      },
      random: () => 0,
    });
    const resources = createAnimatedFlowResources(1);

    pool.update(1);
    pool.configure({
      ...forward,
      rate: 1,
      maxParticles: 1,
      failure: {
        probability: 1,
        burstCount: 1,
        duration: 1,
        color: '#00ff00',
      },
    });
    pool.update(0.5);
    const burst = pool.snapshot()[0];
    writeFlowParticles(resources, points, [burst]);

    expect(burst).toMatchObject({ state: 'burst', failureColor: '#ff0000' });
    expect(
      Array.from(
        (resources.geometry.getAttribute('color') as THREE.BufferAttribute)
          .array
      ).slice(0, 3)
    ).toEqual([1, 0, 0]);
    disposeAnimatedFlowResources(resources);
  });

  it('preserves emitted particles through a mounted lifecycle update with equivalent fresh points', () => {
    const lifecycle = new FlowParticlePoolLifecycle(points, () => 0.5);
    const firstPool = lifecycle.update(points);

    firstPool.configure(forward);
    firstPool.update(0.5);
    const emitted = firstPool.snapshot()[0];
    const updatedPool = lifecycle.update(
      points.map((point) => [...point]) as typeof points
    );

    expect(updatedPool).toBe(firstPool);
    expect(updatedPool.snapshot()[0]).toBe(emitted);
  });

  it('reuses a released particle slot rather than growing a new object pool', () => {
    const pool = new FlowParticlePool({
      points,
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
