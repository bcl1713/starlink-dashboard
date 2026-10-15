import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
import { resolveGfsFlags } from '@/services/gfs-mode';
import type { GfsDrawing, GfsFlags } from './gfs-controller';
import type { WeatherBudget } from './weather-budget';
import { createGridRaster } from './grid-raster';
import { createWindParticleDrawing } from './wind-particle-drawing';
export { earthPoint } from './grid-raster';
export type NativeGridDrawing = GfsDrawing & {
  mode: 'winds' | 'temperature' | 'off';
  update(deltaSeconds: number): void;
  setReducedMotion(reduced: boolean): void;
};
export function createGridDrawing(
  lease: GridLease,
  layers: GfsFlags,
  budget: WeatherBudget,
  options: { reducedMotion?: boolean } = {}
): NativeGridDrawing {
  const flags = resolveGfsFlags(layers);
  const mode = flags.winds
    ? 'winds'
    : flags.temperature
      ? 'temperature'
      : 'off';
  const object = new THREE.Group();
  object.name = 'Native GFS atmosphere';
  let grid: GridLease | undefined = lease,
    raster: GfsDrawing | undefined;
  let particles: ReturnType<typeof createWindParticleDrawing> | undefined;
  const bytes = { decoded: 0, gpu: 0 };
  let owned = true;
  const syncBytes = () => {
    bytes.decoded =
      (raster?.bytes.decoded ?? 0) + (particles?.bytes.decoded ?? 0);
    bytes.gpu = (raster?.bytes.gpu ?? 0) + (particles?.bytes.gpu ?? 0);
  };
  const setReducedMotion = (reduced: boolean) => {
    if (!owned || mode !== 'winds') return;
    if (reduced && particles) {
      object.remove(particles.object);
      particles.dispose();
      particles = undefined;
    } else if (!reduced && !particles && grid) {
      particles = createWindParticleDrawing(grid, budget);
      object.add(particles.object);
    }
    syncBytes();
  };
  const dispose = () => {
    if (!owned) return;
    owned = false;
    object.clear();
    object.userData = {};
    particles?.dispose();
    particles = undefined;
    raster?.dispose();
    raster = undefined;
    grid = undefined;
    syncBytes();
  };
  try {
    if (mode !== 'off') {
      raster = createGridRaster(lease, mode, budget);
      object.add(raster.object);
    }
    object.userData.gfs = {
      mode,
      grid: {
        descriptor: lease.descriptor,
        u: lease.u,
        v: lease.v,
        t: lease.t,
        mask: lease.mask,
      },
      bytes,
      budget: () => budget.snapshot(),
    };
    setReducedMotion(options.reducedMotion ?? false);
    syncBytes();
    return {
      object,
      mode,
      bytes,
      dispose,
      setReducedMotion,
      update(delta) {
        if (owned) particles?.update(delta);
      },
    };
  } catch (error) {
    dispose();
    throw error;
  }
}
