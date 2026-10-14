import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
import { resolveGfsFlags } from '@/services/gfs-mode';
import type { GfsDrawing, GfsFlags } from './gfs-controller';
import type { WeatherBudget } from './weather-budget';
import { createGridRaster } from './grid-raster';
export { earthPoint } from './grid-raster';
export type NativeGridDrawing = GfsDrawing & {
  mode: 'winds' | 'temperature' | 'off';
};
export function createGridDrawing(
  lease: GridLease,
  layers: GfsFlags,
  budget: WeatherBudget
): NativeGridDrawing {
  const flags = resolveGfsFlags(layers);
  const mode = flags.winds
    ? 'winds'
    : flags.temperature
      ? 'temperature'
      : 'off';
  const object = new THREE.Group();
  object.name = 'Native GFS atmosphere';
  const raster =
    mode === 'off' ? undefined : createGridRaster(lease, mode, budget);
  if (raster) object.add(raster.object);
  const bytes = raster?.bytes ?? { decoded: 0, gpu: 0 };
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
  let owned = true;
  return {
    object,
    mode,
    bytes,
    dispose() {
      if (!owned) return;
      owned = false;
      object.clear();
      object.userData = {};
      raster?.dispose();
    },
  };
}
