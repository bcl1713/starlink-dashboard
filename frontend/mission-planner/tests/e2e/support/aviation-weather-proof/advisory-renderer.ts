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
    issuer?: string | null;
    fir_id?: string | null;
    series_id?: string | null;
    hazard?: string | null;
    qualifier?: string | null;
    vertical?: {
      status: string;
      base?: {
        kind: string;
        value: number;
        units?: string;
        reference?: string;
      } | null;
      top?: {
        kind: string;
        value: number;
        units?: string;
        reference?: string;
      } | null;
    };
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
export function advisoryContext(f: Feature) {
  const p = f.properties,
    v = p.vertical;
  const level = (n: NonNullable<Feature['properties']['vertical']>['base']) =>
    n
      ? `${n.kind} ${n.value} ${n.units ?? ''} ${n.reference ?? ''}`.trim()
      : 'unknown';
  const utc = (n: number | null) =>
    n === null ? 'unknown' : new Date(n).toISOString();
  return `Issuer ${p.issuer ?? 'unknown'} • FIR ${p.fir_id ?? 'unknown'} • Series ${p.series_id ?? 'unknown'} • Hazard ${p.hazard ?? 'unknown'} ${p.qualifier ?? ''} • Bulletin validity [${utc(p.validity.start_ms)}, ${utc(p.validity.end_ms)}) UTC • ${v?.status === 'known' ? `vertical ${level(v.base)} → ${level(v.top)}` : 'vertical unknown (base/top units and reference unverified)'}`;
}
export function advisoryMesh(features: Feature[], now: number) {
  const positions: number[] = [],
    outlines: number[] = [];
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
    if (positions.length + outlines.length + 9 > 300_000)
      throw Error('advisory geometry budget');
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
      for (const ring of polygon)
        for (let i = 1; i < ring.length; i++) {
          const a = ring[i - 1],
            b = ring[i],
            steps = Math.max(
              1,
              Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 1)
            );
          if (positions.length + outlines.length + steps * 6 > 300_000)
            throw Error('advisory geometry budget');
          for (let j = 0; j < steps; j++)
            for (const t of [j / steps, (j + 1) / steps])
              outlines.push(
                ...earthPoint(
                  a[1] + (b[1] - a[1]) * t,
                  a[0] + (b[0] - a[0]) * t,
                  2.028
                ).toArray()
              );
        }
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
  const outlineGeometry = new THREE.BufferGeometry();
  outlineGeometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(outlines, 3)
  );
  const outlineMaterial = new THREE.LineBasicMaterial({
    color: 0xffdf91,
    depthWrite: false,
    toneMapped: false,
  });
  const outline = new THREE.LineSegments(outlineGeometry, outlineMaterial);
  outline.name = 'SIGMET exterior and hole outlines';
  outline.renderOrder = 23;
  mesh.add(outline);
  mesh.name = 'Aviation diagnostic active SIGMET';
  mesh.renderOrder = 22;
  return {
    mesh,
    selected,
    triangles,
    bytes: geometryBytes(geometry) + geometryBytes(outlineGeometry),
    outlineVertices: outlines.length / 3,
    dispose: () => {
      geometry.dispose();
      material.dispose();
      outlineGeometry.dispose();
      outlineMaterial.dispose();
    },
  };
}
