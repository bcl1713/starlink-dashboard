import * as THREE from 'three';
import { earthPoint, geometryBytes } from './grid-renderer';
export type Feature = {
  id: string;
  geometry: { type: string; coordinates: number[][][] | number[][][][] } | null;
  properties: {
    validity: { start_ms: number | null; end_ms: number | null };
    cancellation: { cancelled: boolean };
    status: string;
    source_index?: number;
    vertical?: unknown;
  };
};
export function active(feature: Feature, now: number) {
  const p = feature.properties;
  return (
    !p.cancellation.cancelled &&
    p.validity.start_ms !== null &&
    p.validity.end_ms !== null &&
    p.validity.start_ms <= now &&
    now < p.validity.end_ms
  );
}
export function advisoryMesh(features: Feature[], now: number) {
  const positions: number[] = [];
  let triangles = 0;
  // Triangulate planar clipped polygons with holes, then subdivide every triangle
  // internally before projection. This keeps wide interiors above the Earth.
  const triangle = (
    a: THREE.Vector2,
    b: THREE.Vector2,
    c: THREE.Vector2,
    depth = 0
  ) => {
    if (
      Math.max(a.distanceTo(b), b.distanceTo(c), c.distanceTo(a)) > 2 &&
      depth < 10
    ) {
      const ab = a.clone().add(b).multiplyScalar(0.5),
        bc = b.clone().add(c).multiplyScalar(0.5),
        ca = c.clone().add(a).multiplyScalar(0.5);
      triangle(a, ab, ca, depth + 1);
      triangle(ab, b, bc, depth + 1);
      triangle(ca, bc, c, depth + 1);
      triangle(ab, bc, ca, depth + 1);
      return;
    }
    if (positions.length + 9 > 300_000) throw Error('advisory geometry budget');
    for (const p of [a, b, c])
      positions.push(...earthPoint(p.y, p.x, 2.024).toArray());
    triangles++;
  };
  let selected = 0;
  for (const f of features) {
    if (!active(f, now) || !f.geometry) continue;
    selected++;
    const polygons =
      f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates as number[][][]]
        : (f.geometry.coordinates as number[][][][]);
    for (const polygon of polygons) {
      const rings = polygon.map((r) =>
          r.slice(0, -1).map((p) => new THREE.Vector2(p[0], p[1]))
        ),
        all = rings.flat();
      for (const indexes of THREE.ShapeUtils.triangulateShape(
        rings[0],
        rings.slice(1)
      ))
        triangle(all[indexes[0]], all[indexes[1]], all[indexes[2]]);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(positions, 3)
  );
  const material = new THREE.MeshBasicMaterial({
    color: 0xffbf42,
    transparent: true,
    opacity: 0.4,
    side: THREE.DoubleSide,
    depthWrite: false,
    toneMapped: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = 'Aviation diagnostic active SIGMET';
  mesh.renderOrder = 22;
  return {
    mesh,
    selected,
    triangles,
    bytes: geometryBytes(geometry),
    dispose: () => {
      geometry.dispose();
      material.dispose();
    },
  };
}
