import * as THREE from 'three';
import {
  activeFeatures,
  currentForecastGroups,
  forecastCategory,
  type AviationCollection,
  type AviationStation,
  type AviationAdvisory,
} from '@/services/aviation-features';
import type { AviationLayer } from '@/services/aviation-weather';
export const earthPoint = (lat: number, lon: number, radius = 2.026) => {
  const a = (lat * Math.PI) / 180,
    b = (lon * Math.PI) / 180;
  return new THREE.Vector3(
    radius * Math.cos(a) * Math.cos(b),
    radius * Math.sin(a),
    -radius * Math.cos(a) * Math.sin(b)
  );
};
export type AviationDrawing = {
  object: THREE.Object3D;
  bytes: number;
  dispose: () => void;
};
const colors = {
  VFR: '#4ade80',
  MVFR: '#60a5fa',
  IFR: '#f87171',
  LIFR: '#c084fc',
  unknown: '#9ca3af',
};
export function createAviationDrawing(
  c: AviationCollection,
  layer: AviationLayer,
  now: number
): AviationDrawing {
  if (layer === 'sigmet')
    return advisoryDrawing(activeFeatures(c, layer, now) as AviationAdvisory[]);
  const positions: number[] = [],
    rgb: number[] = [];
  for (const f of activeFeatures(c, layer, now) as AviationStation[]) {
    const [lon, lat] = f.geometry.coordinates,
      center = earthPoint(lat, lon);
    const groups = currentForecastGroups(f, now);
    // Alternatives retain their own detail; a marker only reports agreement
    // among the currently valid groups, never the original TAF base category.
    const categories = groups.map(forecastCategory);
    const category =
      layer === 'taf'
        ? categories.length && categories.every((v) => v === categories[0])
          ? categories[0]
          : null
        : f.properties.flight_category;
    const color = new THREE.Color(colors[category ?? 'unknown']);
    if (layer === 'metar') {
      positions.push(...center.toArray());
      rgb.push(color.r, color.g, color.b);
    } else {
      const normal = center.clone().normalize(),
        east = new THREE.Vector3(
          -Math.sin((lon * Math.PI) / 180),
          0,
          -Math.cos((lon * Math.PI) / 180)
        ),
        north = normal.clone().cross(east).normalize();
      const corners = [
        north,
        east,
        north.clone().negate(),
        east.clone().negate(),
      ].map((v) =>
        center
          .clone()
          .addScaledVector(v, 0.008)
          .normalize()
          .multiplyScalar(2.026)
      );
      for (let i = 0; i < 4; i++)
        for (const p of [corners[i], corners[(i + 1) % 4]]) {
          positions.push(...p.toArray());
          rgb.push(color.r, color.g, color.b);
        }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    'position',
    new THREE.Float32BufferAttribute(positions, 3)
  );
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(rgb, 3));
  const material =
    layer === 'metar'
      ? new THREE.PointsMaterial({
          size: 0.013,
          sizeAttenuation: true,
          vertexColors: true,
          toneMapped: false,
          depthWrite: false,
        })
      : new THREE.LineBasicMaterial({
          vertexColors: true,
          toneMapped: false,
          depthWrite: false,
        });
  const object =
    layer === 'metar'
      ? new THREE.Points(geometry, material as THREE.PointsMaterial)
      : new THREE.LineSegments(geometry, material as THREE.LineBasicMaterial);
  object.renderOrder = 24;
  object.name =
    layer === 'metar'
      ? 'Native METAR / SPECI observations'
      : 'Native TAF terminal forecasts';
  return {
    object,
    bytes: (positions.length + rgb.length) * 4,
    dispose: () => {
      geometry.dispose();
      material.dispose();
    },
  };
}
function advisoryDrawing(features: AviationAdvisory[]): AviationDrawing {
  const positions: number[] = [],
    outlines: number[] = [];
  const admit = (extra: number) => {
    if (positions.length + outlines.length + extra > 300000)
      throw Error('Advisory rendered vertex budget');
  };
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
    admit(9);
    for (const p of [a, b, c])
      positions.push(...earthPoint(p.y, p.x, 2.026).toArray());
  };
  for (const f of features) {
    if (!f.geometry) continue;
    const polygons =
      f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates]
        : f.geometry.coordinates;
    for (const polygon of polygons) {
      for (const ring of polygon)
        for (let i = 1; i < ring.length; i++) {
          const a = ring[i - 1],
            b = ring[i],
            steps = Math.max(
              1,
              Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]))
            );
          admit(steps * 6);
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
      const faces = THREE.ShapeUtils.triangulateShape(rings[0], rings.slice(1));
      const area = (ring: THREE.Vector2[]) =>
        Math.abs(
          ring.reduce((sum, p, i) => {
            const q = ring[(i + 1) % ring.length];
            return sum + p.x * q.y - q.x * p.y;
          }, 0) / 2
        );
      const expectedArea =
        area(rings[0]) - rings.slice(1).reduce((sum, r) => sum + area(r), 0);
      const triangleArea = faces.reduce((sum, [ia, ib, ic]) => {
        const a = all[ia],
          b = all[ib],
          c = all[ic];
        return (
          sum +
          Math.abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)) / 2
        );
      }, 0);
      if (
        !faces.length ||
        expectedArea <= 0 ||
        Math.abs(triangleArea - expectedArea) >
          Math.max(1e-9, expectedArea * 1e-8)
      )
        throw Error('Invalid advisory tessellation topology');
      for (const indexes of faces)
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
    opacity: 0.32,
    side: THREE.DoubleSide,
    depthWrite: false,
    toneMapped: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = 22;
  mesh.name = 'Native international SIGMET advisories';
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
  outline.renderOrder = 23;
  mesh.add(outline);
  return {
    object: mesh,
    bytes: (positions.length + outlines.length) * 4,
    dispose: () => {
      geometry.dispose();
      material.dispose();
      outlineGeometry.dispose();
      outlineMaterial.dispose();
    },
  };
}
