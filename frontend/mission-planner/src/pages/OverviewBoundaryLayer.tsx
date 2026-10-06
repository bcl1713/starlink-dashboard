import { useEffect, useMemo } from 'react';
import { useThree } from '@react-three/fiber';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import type { BoundaryKind, projectBoundaries } from './overview-boundaries';

export function OverviewBoundaryLayer({
  kind,
  segments,
}: {
  kind: BoundaryKind;
  segments: ReturnType<typeof projectBoundaries>;
}) {
  const { width, height } = useThree((state) => state.size);
  const batch = useMemo(() => {
    const geometries: LineSegmentsGeometry[] = [];
    const materials: LineMaterial[] = [];
    const objects: LineSegments2[] = [];
    for (const [disputed, positions] of [
      [false, segments.standard],
      [true, segments.disputed],
    ] as const) {
      if (positions.length === 0) continue;
      const geometry = new LineSegmentsGeometry();
      geometry.setPositions(positions);
      geometries.push(geometry);
      // Two screen-space strokes keep reference lines readable over bright land
      // and dark oceans without competing with the colored operational layers.
      for (const halo of [true, false]) {
        const material = new LineMaterial({
          color: halo
            ? '#10151d'
            : kind === 'countries'
              ? '#dde4ee'
              : '#9aaebf',
          linewidth: halo
            ? kind === 'countries'
              ? 3
              : 2.5
            : kind === 'countries'
              ? 1.2
              : 0.8,
          opacity: halo ? 0.45 : kind === 'countries' ? 0.85 : 0.6,
          transparent: true,
          depthTest: true,
          depthWrite: false,
          toneMapped: false,
          dashed: disputed,
          dashScale: 1,
          dashSize: 0.015,
          gapSize: 0.01,
        });
        const object = new LineSegments2(geometry, material);
        object.computeLineDistances();
        object.renderOrder = halo ? -4 : -3;
        object.raycast = () => {};
        object.name = `overview-boundaries-${kind}${disputed ? '-disputed' : ''}${halo ? '-halo' : ''}`;
        materials.push(material);
        objects.push(object);
      }
    }
    return { geometries, materials, objects };
  }, [kind, segments]);
  useEffect(() => {
    for (const material of batch.materials)
      material.resolution.set(width, height);
  }, [batch, width, height]);
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
