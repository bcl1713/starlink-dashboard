import * as THREE from 'three';
import type { GridLease } from '@/services/aviation-grid';
export function barb(u: number, v: number) {
  const speed = Math.hypot(u, v),
    knots = Math.round((speed * 1.9438444924406) / 5) * 5;
  return {
    knots,
    calm: knots === 0,
    flags: Math.floor(knots / 50),
    full: Math.floor((knots % 50) / 10),
    half: knots % 10 >= 5 ? 1 : 0,
    fromEast: speed && u ? -u / speed : 0,
    fromNorth: speed && v ? -v / speed : 0,
  };
}
export function windFrame(lat: number, lon: number, u: number, v: number) {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180,
    g = barb(u, v);
  const east = new THREE.Vector3(-Math.sin(b), 0, -Math.cos(b));
  const north = new THREE.Vector3(
    -Math.sin(a) * Math.cos(b),
    Math.cos(a),
    Math.sin(a) * Math.sin(b)
  );
  return {
    east,
    north,
    shaft: east
      .clone()
      .multiplyScalar(g.fromEast)
      .addScaledVector(north, g.fromNorth),
  };
}
export function windSamples(lease: GridLease) {
  const samples = [];
  const seen = new Set<number>();
  for (let i = 0; i < 2000; i++) {
    const lat = (Math.asin(1 - (2 * (i + 0.5)) / 2000) * 180) / Math.PI,
      lon = ((i * 137.50776405003785 + 180) % 360) - 180;
    const row = Math.round((90 - lat) * 2),
      col = Math.round((lon + 180) * 2) % 720,
      index = row * 720 + col;
    if (seen.has(index) || lease.mask[index]) continue;
    seen.add(index);
    const c = lease.descriptor.grid.components;
    const u = lease.u[index] * c[0].scale! + c[0].offset!,
      v = lease.v[index] * c[1].scale! + c[1].offset!;
    samples.push({
      row,
      col,
      lat: 90 - row * 0.5,
      lon: -180 + col * 0.5,
      u,
      v,
      ...barb(u, v),
    });
  }
  return samples;
}
