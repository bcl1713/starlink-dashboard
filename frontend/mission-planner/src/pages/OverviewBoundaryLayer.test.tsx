/** @vitest-environment jsdom */
import { create } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { OverviewBoundaryLayer } from './OverviewBoundaryLayer';
import { parseBoundaries, projectBoundaries } from './overview-boundaries';
it('batches border segments, preserves earth occlusion and releases GPU resources on disable', async () => {
  const segments = projectBoundaries(
    parseBoundaries({
      version: 1,
      lines: [
        {
          disputed: false,
          points: [
            [0, 0],
            [1, 0],
          ],
        },
        {
          disputed: true,
          points: [
            [2, 0],
            [3, 0],
          ],
        },
      ],
    })
  );
  const geometry = vi.spyOn(THREE.BufferGeometry.prototype, 'dispose');
  const material = vi.spyOn(THREE.Material.prototype, 'dispose');
  const view = await create(
    <OverviewBoundaryLayer kind="countries" segments={segments} />
  );
  const borders = view.scene.instance.children[0]
    .children as THREE.LineSegments[];
  expect(borders).toHaveLength(2);
  for (const border of borders) {
    expect(border.isLineSegments).toBe(true);
    expect(border.geometry.attributes.position.count).toBeGreaterThan(0);
    const mat = border.material as THREE.Material;
    expect(mat.depthTest).toBe(true);
    expect(mat.depthWrite).toBe(false);
    expect(border.raycast(new THREE.Raycaster(), [])).toBeUndefined();
  }
  const objects = [...borders];
  await view.update(
    <OverviewBoundaryLayer kind="countries" segments={segments} />
  );
  expect(view.scene.instance.children[0].children).toEqual(objects);
  expect(borders[1].material).toBeInstanceOf(THREE.LineDashedMaterial);
  await view.unmount();
  expect(geometry).toHaveBeenCalledTimes(2);
  expect(material).toHaveBeenCalledTimes(2);
  vi.restoreAllMocks();
});
