import { Matrix4, Ray, Sphere, Vector3 } from 'three';
import type { WeatherCapabilities } from '@/services/overview-weather';
import { weatherUvFromPosition } from './weather-projection';

export type DetailKey = { z: number; x: number; y: number };
export type CameraSnapshot = {
  projection: readonly number[];
  cameraWorld: readonly number[];
  globeWorld: readonly number[];
  drawingBuffer: readonly [number, number];
};
export type DetailDemand = {
  keys: readonly DetailKey[];
  level: number;
  texelPixels: number;
};
export const detailKey = (key: DetailKey) => `${key.z}/${key.x}/${key.y}`;
export const demandIdentity = (demand: DetailDemand) =>
  demand.keys.map(detailKey).sort().join(',');
const empty = (): DetailDemand => ({ keys: [], level: 2, texelPixels: 0 });

/** Sample native screen rays in globe space; reject occluded/foreshortened hits. */
export function selectDetail(
  snapshot: CameraSnapshot,
  capabilities: WeatherCapabilities,
  previous: DetailDemand | null
): DetailDemand {
  if (
    capabilities.tile_schema !== 'xyz-rgba-pair-v1' ||
    capabilities.coverage_encoding !== 'absence-rgba-v1' ||
    capabilities.tile_size !== 512 ||
    capabilities.max_zoom < 3
  )
    return empty();
  const [width, height] = snapshot.drawingBuffer;
  if (
    !(width > 0 && height > 0) ||
    [snapshot.projection, snapshot.cameraWorld, snapshot.globeWorld].some(
      (matrix) =>
        matrix.length !== 16 || matrix.some((value) => !Number.isFinite(value))
    )
  )
    return empty();
  const projection = new Matrix4().fromArray(snapshot.projection);
  const camera = new Matrix4().fromArray(snapshot.cameraWorld);
  const globe = new Matrix4().fromArray(snapshot.globeWorld);
  if (
    !projection.determinant() ||
    !camera.determinant() ||
    !globe.determinant()
  )
    return empty();
  const inverseGlobe = globe.clone().invert();
  const unproject = inverseGlobe
    .clone()
    .multiply(camera)
    .multiply(projection.clone().invert());
  const toScreen = projection
    .clone()
    .multiply(camera.clone().invert())
    .multiply(globe);
  const origin = new Vector3()
    .setFromMatrixPosition(camera)
    .applyMatrix4(inverseGlobe);
  const sphere = new Sphere(new Vector3(), 2);
  const hits: { u: number; v: number; resolution: number; weight: number }[] =
    [];
  for (let row = 0; row <= 16; row++)
    for (let col = 0; col <= 24; col++) {
      const sx = col / 12 - 1,
        sy = row / 8 - 1;
      const far = new Vector3(sx, sy, 0.5).applyMatrix4(unproject);
      const ray = new Ray(origin, far.sub(origin).normalize());
      const point = ray.intersectSphere(sphere, new Vector3());
      if (!point) continue;
      const facing = -point.clone().normalize().dot(ray.direction);
      if (facing < 0.25) continue;
      const uv = weatherUvFromPosition(point.toArray());
      if (!uv) continue;
      const lat = Math.asin(point.y / 2),
        lon = Math.atan2(-point.z, point.x);
      const step = 1 / (4 * capabilities.tile_size);
      const shifted = new Vector3(
        2 * Math.cos(lat) * Math.cos(lon + step * 2 * Math.PI),
        2 * Math.sin(lat),
        -2 * Math.cos(lat) * Math.sin(lon + step * 2 * Math.PI)
      );
      const a = point.clone().applyMatrix4(toScreen),
        b = shifted.applyMatrix4(toScreen);
      const resolution = Math.hypot(
        ((b.x - a.x) * width) / 2,
        ((b.y - a.y) * height) / 2
      );
      hits.push({
        u: uv[0],
        v: uv[1],
        resolution,
        weight: facing * (1.1 - 0.25 * (sx * sx + sy * sy)),
      });
    }
  if (!hits.length) return empty();
  const resolution =
    hits.reduce((sum, hit) => sum + hit.resolution * hit.weight, 0) /
    hits.reduce((sum, hit) => sum + hit.weight, 0);
  let level = Math.min(
    capabilities.max_zoom,
    Math.max(2, 2 + Math.ceil(Math.log2(Math.max(0.01, resolution))))
  );
  if (previous && previous.level <= capabilities.max_zoom) {
    const oldPixels = resolution / 2 ** (previous.level - 2);
    if (oldPixels >= 0.8 && oldPixels <= 1.2) level = previous.level;
  }
  if (level <= 2) return empty();
  const collect = (z: number) => {
    const n = 2 ** z,
      keys = new Map<string, { key: DetailKey; weight: number }>();
    for (const hit of hits) {
      const key = {
        z,
        x: Math.min(n - 1, Math.floor(hit.u * n)),
        y: Math.min(n - 1, Math.floor(hit.v * n)),
      };
      const id = detailKey(key),
        old = keys.get(id);
      keys.set(id, { key, weight: (old?.weight ?? 0) + hit.weight });
    }
    return [...keys.values()];
  };
  let ranked = collect(level);
  while (ranked.length > 8 && level > 3) ranked = collect(--level);
  const retained = new Set(previous?.keys.map(detailKey));
  ranked.sort(
    (a, b) =>
      b.weight * (retained.has(detailKey(b.key)) ? 1.2 : 1) -
        a.weight * (retained.has(detailKey(a.key)) ? 1.2 : 1) ||
      detailKey(a.key).localeCompare(detailKey(b.key))
  );
  return {
    keys: ranked
      .slice(0, 8)
      .map((item) => item.key)
      .sort((a, b) => detailKey(a).localeCompare(detailKey(b))),
    level,
    texelPixels: resolution / 2 ** (level - 2),
  };
}

/** One pending demand; monotonic elapsed time, never a history of camera positions. */
export class DetailDemandStabilizer {
  private pending: DetailDemand | null = null;
  private since = 0;
  private emitted = '';
  update(demand: DetailDemand, nowMono: number): DetailDemand | null {
    const id = demandIdentity(demand);
    if (id === this.emitted) {
      this.pending = null;
      return null;
    }
    if (!this.pending || demandIdentity(this.pending) !== id) {
      this.pending = demand;
      this.since = nowMono;
      return null;
    }
    if (nowMono - this.since < 400) return null;
    this.emitted = id;
    this.pending = null;
    return demand;
  }
}
