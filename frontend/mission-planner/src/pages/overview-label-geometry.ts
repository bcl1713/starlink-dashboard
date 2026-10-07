import * as THREE from 'three';
import type { LabelBounds, LabelLeader } from './overview-label-layout';
import type { FlowPoint } from './overview-animated-flow-line-rendering';
import { isStarMarkerVisible } from './overview-star-marker-rendering';

const scratch = new THREE.Vector3();
const VISIBILITY_MARGIN = 8;

/** Read the matrix and shader extent used in the just-rendered frame. This
 * includes the complete rotated halo, regardless of marker/glow slider values. */
export function projectOverviewAircraftBounds(
  scene: THREE.Scene,
  camera: THREE.Camera,
  viewport: { width: number; height: number }
): LabelBounds[] {
  const marker = scene.getObjectByName('overview-own-aircraft') as
    | THREE.Mesh
    | undefined;
  if (!marker) return [];
  for (
    let parent: THREE.Object3D | null = marker;
    parent;
    parent = parent.parent
  )
    if (!parent.visible) return [];
  const halo = marker.children[0] as THREE.Mesh;
  const extent = Math.max(
    1,
    (halo?.material as THREE.ShaderMaterial)?.uniforms?.uExtent?.value ?? 1
  );
  let left = Infinity,
    top = Infinity,
    right = -Infinity,
    bottom = -Infinity;
  for (const x of [-extent, extent])
    for (const y of [-extent, extent]) {
      scratch.set(x, y, 0).applyMatrix4(marker.matrixWorld).project(camera);
      if (!Number.isFinite(scratch.x) || !Number.isFinite(scratch.y)) return [];
      const px = ((scratch.x + 1) * viewport.width) / 2,
        py = ((1 - scratch.y) * viewport.height) / 2;
      left = Math.min(left, px);
      right = Math.max(right, px);
      top = Math.min(top, py);
      bottom = Math.max(bottom, py);
    }
  return [
    {
      x: left - VISIBILITY_MARGIN,
      y: top - VISIBILITY_MARGIN,
      width: right - left + 2 * VISIBILITY_MARGIN,
      height: bottom - top + 2 * VISIBILITY_MARGIN,
    },
  ];
}

export function projectOverviewPaths(
  paths: readonly (readonly FlowPoint[])[],
  camera: THREE.Camera,
  viewport: { width: number; height: number }
): LabelLeader[] {
  const segments: LabelLeader[] = [];
  for (const path of paths) {
    let previous: { x: number; y: number } | null = null;
    for (const point of path) {
      scratch.set(...point);
      if (!isStarMarkerVisible(scratch, camera)) {
        previous = null;
        continue;
      }
      scratch.project(camera);
      if (scratch.z < -1 || scratch.z > 1) {
        previous = null;
        continue;
      }
      const projected = {
        x: ((scratch.x + 1) * viewport.width) / 2,
        y: ((1 - scratch.y) * viewport.height) / 2,
      };
      if (previous) segments.push({ start: previous, end: projected });
      previous = projected;
    }
  }
  return segments;
}
