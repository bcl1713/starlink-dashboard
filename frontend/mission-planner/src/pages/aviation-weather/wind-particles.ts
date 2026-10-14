import type { GridLease } from '@/services/aviation-grid';
import { sampleWindInto } from './grid-sampling';

export const MAX_WIND_PARTICLES = 2000;
export const WIND_TRAIL_SAMPLES = 12;
const SAMPLE_INTERVAL = 1 / 30,
  STEP = 1 / 120,
  MOTION = 12000 / 6371000;
const DEGREES = 180 / Math.PI,
  RADIUS = 2.014,
  EPSILON = 1e-12;

export type WindParticleState = {
  grid?: GridLease;
  instanceId: string;
  count: number;
  randomState: number;
  points: Float64Array;
  history: Float64Array;
  ages: Float64Array;
  lifetimes: Float64Array;
  heads: Uint8Array;
  lengths: Uint8Array;
  attempts: Uint8Array;
  positions: Float32Array;
  alpha: Float32Array;
  sample: Float64Array;
  sampleAccumulator: number;
  vertexCount: number;
  available: boolean;
};

/** Complete retained typed-array footprint, including the reusable sample. */
export const WIND_PARTICLE_BYTES = {
  decoded:
    MAX_WIND_PARTICLES *
      (3 * 8 +
        WIND_TRAIL_SAMPLES * 3 * 8 +
        2 * 8 +
        3 +
        (WIND_TRAIL_SAMPLES - 1) * 2 * 4 * 4) +
    3 * 8,
  gpu: MAX_WIND_PARTICLES * (WIND_TRAIL_SAMPLES - 1) * 2 * 4 * 4,
};
function random(s: WindParticleState): number {
  let n = s.randomState;
  n ^= n << 13;
  n ^= n >>> 17;
  n ^= n << 5;
  s.randomState = n >>> 0;
  return s.randomState / 4294967296;
}
function sample(s: WindParticleState, x: number, y: number, z: number): void {
  sampleWindInto(
    s.grid!,
    Math.atan2(y, Math.hypot(x, z)) * DEGREES,
    Math.atan2(-z, x) * DEGREES,
    s.sample
  );
}
function resetHistory(s: WindParticleState, i: number): void {
  const p = i * 3,
    h = i * WIND_TRAIL_SAMPLES * 3;
  s.history.fill(0, h, h + WIND_TRAIL_SAMPLES * 3);
  s.history[h] = s.points[p];
  s.history[h + 1] = s.points[p + 1];
  s.history[h + 2] = s.points[p + 2];
  s.heads[i] = 0;
  s.lengths[i] = 1;
}
function seed(s: WindParticleState, i: number, initial = false): boolean {
  while (s.attempts[i] < 4) {
    const first = initial && s.attempts[i] === 0;
    s.attempts[i]++;
    const lat = Math.asin(
      first ? 1 - (2 * (i + 0.5)) / s.count : 1 - 2 * random(s)
    );
    const lon =
      ((first
        ? i * 137.50776405003785 + (s.randomState % 360)
        : random(s) * 360) -
        180) /
      DEGREES;
    sampleWindInto(s.grid!, lat * DEGREES, lon * DEGREES, s.sample);
    if (s.sample[2]) continue;
    const p = i * 3;
    s.points[p] = Math.cos(lat) * Math.cos(lon);
    s.points[p + 1] = Math.sin(lat);
    s.points[p + 2] = -Math.cos(lat) * Math.sin(lon);
    s.lifetimes[i] = 3 + random(s) * 3;
    s.ages[i] = initial ? random(s) * s.lifetimes[i] : 0;
    resetHistory(s, i);
    return true;
  }
  s.lengths[i] = 0;
  return false;
}
export function createWindParticles(grid: GridLease): WindParticleState {
  const n = MAX_WIND_PARTICLES,
    vertices = n * (WIND_TRAIL_SAMPLES - 1) * 2;
  const s: WindParticleState = {
    grid,
    instanceId: grid.descriptor.instance_id,
    count: n,
    randomState:
      Number.parseInt(grid.descriptor.instance_id.slice(0, 8), 16) ||
      0x6d2b79f5,
    points: new Float64Array(n * 3),
    history: new Float64Array(n * WIND_TRAIL_SAMPLES * 3),
    ages: new Float64Array(n),
    lifetimes: new Float64Array(n),
    heads: new Uint8Array(n),
    lengths: new Uint8Array(n),
    attempts: new Uint8Array(n),
    positions: new Float32Array(vertices * 3),
    alpha: new Float32Array(vertices),
    sample: new Float64Array(3),
    sampleAccumulator: 0,
    vertexCount: 0,
    available: grid.mask.some((mask) => mask === 0),
  };
  if (s.available) for (let i = 0; i < n; i++) seed(s, i, true);
  return s;
}
/** Validate the actual short globe segment; cap work even at polar longitude jumps. */
function clearPath(
  s: WindParticleState,
  ax: number,
  ay: number,
  az: number,
  bx: number,
  by: number,
  bz: number
): boolean {
  const latA = Math.atan2(ay, Math.hypot(ax, az)) * DEGREES,
    latB = Math.atan2(by, Math.hypot(bx, bz)) * DEGREES;
  const lonA = Math.atan2(-az, ax) * DEGREES,
    lonB = Math.atan2(-bz, bx) * DEGREES;
  const span = Math.max(
    Math.abs(latB - latA),
    Math.abs(((lonB - lonA + 540) % 360) - 180)
  );
  const steps = Math.max(1, Math.ceil(span / 0.25));
  if (steps > 8) return false;
  for (let j = 1; j < steps; j++) {
    const f = j / steps;
    sample(s, ax + (bx - ax) * f, ay + (by - ay) * f, az + (bz - az) * f);
    if (s.sample[2]) return false;
  }
  return true;
}
function advancePoint(s: WindParticleState, i: number, dt: number): void {
  if ((!s.lengths[i] || s.ages[i] >= s.lifetimes[i]) && !seed(s, i)) return;
  const p = i * 3,
    x = s.points[p],
    y = s.points[p + 1],
    z = s.points[p + 2];
  sample(s, x, y, z);
  if (s.sample[2]) {
    s.lengths[i] = 0;
    return;
  }
  const u = s.sample[0],
    v = s.sample[1];
  s.ages[i] += dt;
  if (u === 0 && v === 0) return;
  const lon = Math.atan2(-z, x),
    lat = Math.atan2(y, Math.hypot(x, z));
  const sinLon = Math.sin(lon),
    cosLon = Math.cos(lon),
    sinLat = Math.sin(lat),
    cosLat = Math.cos(lat),
    k = dt * MOTION;
  let nx = x + k * (-u * sinLon - v * sinLat * cosLon),
    ny = y + k * v * cosLat,
    nz = z + k * (-u * cosLon + v * sinLat * sinLon);
  const norm = Math.hypot(nx, ny, nz);
  nx /= norm;
  ny /= norm;
  nz /= norm;
  sample(s, nx, ny, nz);
  if (s.sample[2] || !clearPath(s, x, y, z, nx, ny, nz)) {
    s.lengths[i] = 0;
    return;
  }
  s.points[p] = nx;
  s.points[p + 1] = ny;
  s.points[p + 2] = nz;
}
function appendHistory(s: WindParticleState): void {
  for (let i = 0; i < s.count; i++) {
    if (!s.lengths[i]) continue;
    const p = i * 3,
      previous = (i * WIND_TRAIL_SAMPLES + s.heads[i]) * 3;
    if (
      !clearPath(
        s,
        s.history[previous],
        s.history[previous + 1],
        s.history[previous + 2],
        s.points[p],
        s.points[p + 1],
        s.points[p + 2]
      )
    ) {
      resetHistory(s, i);
      continue;
    }
    s.heads[i] = (s.heads[i] + 1) % WIND_TRAIL_SAMPLES;
    s.lengths[i] = Math.min(WIND_TRAIL_SAMPLES, s.lengths[i] + 1);
    const h = (i * WIND_TRAIL_SAMPLES + s.heads[i]) * 3;
    s.history[h] = s.points[p];
    s.history[h + 1] = s.points[p + 1];
    s.history[h + 2] = s.points[p + 2];
  }
}
function writeTrails(s: WindParticleState): void {
  let vertex = 0;
  for (let i = 0; i < s.count; i++) {
    const n = s.lengths[i],
      oldest = (s.heads[i] - n + 1 + WIND_TRAIL_SAMPLES) % WIND_TRAIL_SAMPLES;
    const fade = Math.max(
      0,
      Math.min(1, s.ages[i] / 0.3, (s.lifetimes[i] - s.ages[i]) / 0.5)
    );
    for (let j = 0; j < n - 1; j++) {
      const a =
        (i * WIND_TRAIL_SAMPLES + ((oldest + j) % WIND_TRAIL_SAMPLES)) * 3;
      const b =
        (i * WIND_TRAIL_SAMPLES + ((oldest + j + 1) % WIND_TRAIL_SAMPLES)) * 3;
      if (
        Math.hypot(
          s.history[a] - s.history[b],
          s.history[a + 1] - s.history[b + 1],
          s.history[a + 2] - s.history[b + 2]
        ) <= 1e-12
      )
        continue;
      const p = vertex * 3;
      s.positions[p] = s.history[a] * RADIUS;
      s.positions[p + 1] = s.history[a + 1] * RADIUS;
      s.positions[p + 2] = s.history[a + 2] * RADIUS;
      s.positions[p + 3] = s.history[b] * RADIUS;
      s.positions[p + 4] = s.history[b + 1] * RADIUS;
      s.positions[p + 5] = s.history[b + 2] * RADIUS;
      s.alpha[vertex] = (fade * j) / (WIND_TRAIL_SAMPLES - 1);
      s.alpha[vertex + 1] = (fade * (j + 1)) / (WIND_TRAIL_SAMPLES - 1);
      vertex += 2;
    }
  }
  s.vertexCount = vertex;
}
export function advanceWindParticles(
  s: WindParticleState,
  deltaSeconds: number
): void {
  if (
    !s.grid ||
    !s.available ||
    !Number.isFinite(deltaSeconds) ||
    deltaSeconds <= 0
  )
    return;
  s.attempts.fill(0);
  let remaining = Math.min(deltaSeconds, 0.05);
  while (remaining > EPSILON) {
    const dt = Math.min(STEP, remaining, SAMPLE_INTERVAL - s.sampleAccumulator);
    for (let i = 0; i < s.count; i++) advancePoint(s, i, dt);
    s.sampleAccumulator += dt;
    remaining -= dt;
    if (s.sampleAccumulator >= SAMPLE_INTERVAL - EPSILON) {
      appendHistory(s);
      s.sampleAccumulator = 0;
    }
  }
  writeTrails(s);
}
