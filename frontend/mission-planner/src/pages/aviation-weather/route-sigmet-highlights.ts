import * as THREE from 'three';
import type {
  AviationFeature,
  AviationAdvisory,
} from '@/services/aviation-features';
import type { RouteSigmetEntry, SelectedSigmetEntry } from '@/services/route-sigmets';
import { earthPoint, type AviationDrawing } from './aviation-renderer';
import { weatherKey, type WeatherBudget } from './weather-budget';

export type SigmetRoutePoint = Readonly<{
  longitude: number;
  latitude: number;
}>;
export type SigmetNotice = {
  entry: RouteSigmetEntry | SelectedSigmetEntry;
  reports: AviationFeature[];
  label: string;
  color: string;
  intersectionUnknown?: boolean;
};
const radians = Math.PI / 180;
const textureBytes = 512 * 64 * 4;

/** Each span is evaluated on the original shortest spherical route arc. */
function arc(a: SigmetRoutePoint | undefined, b: SigmetRoutePoint | undefined) {
  if (!a || !b) throw Error('Route span geometry unavailable');
  const u = earthPoint(a.latitude, a.longitude, 1),
    v = earthPoint(b.latitude, b.longitude, 1),
    angle = Math.atan2(u.clone().cross(v).length(), u.dot(v));
  if (!Number.isFinite(angle) || angle < 1e-12 || Math.PI - angle <= 1e-10)
    throw Error('Ambiguous route arc');
  const w = v
    .clone()
    .addScaledVector(u, -Math.cos(angle))
    .divideScalar(Math.sin(angle));
  return {
    angle,
    at: (fraction: number) =>
      u
        .clone()
        .multiplyScalar(Math.cos(angle * fraction))
        .addScaledVector(w, Math.sin(angle * fraction))
        .multiplyScalar(2.033),
  };
}

/** Owns one notice's outlines, separate witnessed spans and a depth-tested label. */
export function createSigmetHighlights(
  notice: SigmetNotice,
  points: readonly SigmetRoutePoint[],
  budget: WeatherBudget
): AviationDrawing {
  let ringCount = 0;
  for (const report of notice.reports as AviationAdvisory[]) {
    if (report.geometry?.type === 'Polygon')
      ringCount += report.geometry.coordinates.length;
    else if (report.geometry)
      for (const polygon of report.geometry.coordinates)
        ringCount += polygon.length;
  }
  // Reserve before constructing arc closures/vectors or native objects. Many
  // point contacts use few vertices but still require independent Line owners.
  const overhead = budget.reserve(weatherKey('sigmet-highlight-objects'), {
    encoded: 0,
    decoded: ('spans' in notice.entry ? notice.entry.spans : []).length * 4096 + ringCount * 32 + 65536,
    gpu: 0,
  });
  try {
    const spans = ('spans' in notice.entry ? notice.entry.spans : []).map((span) => {
      const routeArc = arc(
        points[span.segment_index],
        points[span.segment_index + 1]
      );
      return {
        span,
        arc: routeArc,
        steps: Math.max(
          1,
          Math.ceil(
            (routeArc.angle * (span.end_fraction - span.start_fraction)) /
              radians
          )
        ),
      };
    });
    if (!spans.length && 'spans' in notice.entry) throw Error('Confirmed route spans unavailable');
    const rings = (notice.reports as AviationAdvisory[]).flatMap((report) => {
      const geometry = report.geometry;
      return !geometry
        ? []
        : (geometry.type === 'Polygon'
            ? [geometry.coordinates]
            : geometry.coordinates
          ).flat();
    });
    if (!rings.length) throw Error('Advisory outline unavailable');
    let scalars = spans.reduce(
      (total, span) => total + (span.steps + 1) * 3,
      0
    );
    for (const ring of rings)
      for (let i = 1; i < ring.length; i++)
        scalars +=
          Math.max(
            1,
            Math.ceil(
              Math.hypot(
                ring[i][0] - ring[i - 1][0],
                ring[i][1] - ring[i - 1][1]
              )
            )
          ) * 6;
    if (scalars > 300000) throw Error('Highlight geometry budget');
    const allocation = budget.reserve(weatherKey('sigmet-highlight'), {
      encoded: 0,
      decoded: scalars * 24 + textureBytes * 2 + 65536,
      gpu: scalars * 4 + textureBytes + 4096,
    });
    const group = new THREE.Group();
    group.name = `Route advisory · ${notice.label}`;
    const geometries: THREE.BufferGeometry[] = [],
      materials: THREE.Material[] = [];
    let texture: THREE.CanvasTexture | undefined,
      owned = true;
    const dispose = () => {
      if (!owned) return;
      owned = false;
      geometries.forEach((g) => g.dispose());
      materials.forEach((m) => m.dispose());
      texture?.dispose();
      allocation.release();
      overhead.release();
    };
    try {
      const material = new THREE.LineBasicMaterial({
        color: notice.color,
        depthTest: true,
        depthWrite: false,
        toneMapped: false,
      });
      materials.push(material);
      const lines = (positions: number[], segments: boolean, name: string) => {
        const geometry = new THREE.BufferGeometry();
        geometries.push(geometry);
        geometry.setAttribute(
          'position',
          new THREE.Float32BufferAttribute(positions, 3)
        );
        const line = segments
          ? new THREE.LineSegments(geometry, material)
          : new THREE.Line(geometry, material);
        line.name = name;
        line.renderOrder = 26;
        group.add(line);
      };
      const outlines: number[] = [];
      for (const ring of rings)
        for (let i = 1; i < ring.length; i++) {
          const a = ring[i - 1],
            b = ring[i],
            steps = Math.max(
              1,
              Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]))
            );
          for (let j = 0; j < steps; j++)
            for (const t of [j / steps, (j + 1) / steps])
              outlines.push(
                ...earthPoint(
                  a[1] + (b[1] - a[1]) * t,
                  a[0] + (b[0] - a[0]) * t,
                  2.031
                ).toArray()
              );
        }
      lines(outlines, true, 'Route advisory outline');
      for (const { span, arc, steps } of spans) {
        const positions: number[] = [];
        for (let i = 0; i <= steps; i++)
          positions.push(
            ...arc
              .at(
                span.start_fraction +
                  ((span.end_fraction - span.start_fraction) * i) / steps
              )
              .toArray()
          );
        lines(positions, false, 'Confirmed route span');
      }
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 64;
      const context = canvas.getContext('2d');
      if (!context) throw Error('Highlight label unavailable');
      context.fillStyle = '#101c2b';
      context.fillRect(0, 0, 512, 64);
      context.fillStyle = notice.color;
      context.font = '24px sans-serif';
      context.textBaseline = 'middle';
      context.textAlign = 'center';
      context.fillText(notice.label, 256, 32, 500);
      texture = new THREE.CanvasTexture(canvas);
      texture.generateMipmaps = false;
      texture.minFilter = THREE.LinearFilter;
      const spriteMaterial = new THREE.SpriteMaterial({
        map: texture,
        depthTest: true,
        depthWrite: false,
        toneMapped: false,
      });
      materials.push(spriteMaterial);
      const label = new THREE.Sprite(spriteMaterial);
      label.name = notice.label;
      if (spans.length) {
        label.position.copy(spans[0].arc.at((spans[0].span.start_fraction + spans[0].span.end_fraction) / 2));
      } else {
        const center = rings[0].reduce((sum, point) => sum.add(earthPoint(point[1], point[0], 1)), new THREE.Vector3());
        if (center.lengthSq() < 1e-12) center.copy(earthPoint(rings[0][0][1], rings[0][0][0], 1));
        label.position.copy(center.normalize().multiplyScalar(2.033));
      }
      label.scale.set(0.36, 0.045, 1);
      label.renderOrder = 27;
      group.add(label);
      return {
        object: group,
        bytes: scalars * 4 + textureBytes,
        featureAt: () => undefined,
        dispose,
      };
    } catch (error) {
      dispose();
      throw error;
    }
  } catch (error) {
    overhead.release();
    throw error;
  }
}
