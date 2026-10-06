import { useEffect, useMemo } from 'react';
import {
  BufferAttribute,
  BufferGeometry,
  LineBasicMaterial,
  LineDashedMaterial,
  LineSegments,
} from 'three';
import type { BoundaryKind, projectBoundaries } from './overview-boundaries';

export function OverviewBoundaryLayer({
  kind,
  segments,
}: {
  kind: BoundaryKind;
  segments: ReturnType<typeof projectBoundaries>;
}) {
  const batch = useMemo(() => {
    const geometries: BufferGeometry[] = [];
    const materials: LineBasicMaterial[] = [];
    const objects: LineSegments[] = [];
    for (const [disputed, positions] of [
      [false, segments.standard],
      [true, segments.disputed],
    ] as const) {
      if (positions.length === 0) continue;
      const geometry = new BufferGeometry();
      geometry.setAttribute('position', new BufferAttribute(positions, 3));
      geometries.push(geometry);
      // Native one-pixel lines avoid expanding every reference segment into
      // triangles. Operational layers retain their stronger screen-space strokes.
      const style = {
        color: kind === 'countries' ? '#dde4ee' : '#9aaebf',
        opacity: kind === 'countries' ? 0.9 : 0.65,
        transparent: true,
        depthTest: true,
        depthWrite: false,
        toneMapped: false,
      };
      const material = disputed
        ? new LineDashedMaterial({ ...style, dashSize: 0.015, gapSize: 0.01 })
        : new LineBasicMaterial(style);
      const object = new LineSegments(geometry, material);
      if (disputed) object.computeLineDistances();
      object.renderOrder = kind === 'countries' ? -3 : -4;
      object.raycast = () => {};
      object.name = `overview-boundaries-${kind}${disputed ? '-disputed' : ''}`;
      materials.push(material);
      objects.push(object);
    }
    return { geometries, materials, objects };
  }, [kind, segments]);
  useEffect(
    () => () => {
      batch.geometries.forEach((geometry) => geometry.dispose());
      batch.materials.forEach((material) => material.dispose());
    },
    [batch]
  );
  return (
    <group dispose={null}>
      {batch.objects.map((object) => (
        <primitive key={object.name} object={object} />
      ))}
    </group>
  );
}
