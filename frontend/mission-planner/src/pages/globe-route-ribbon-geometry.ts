import * as THREE from 'three';
import type { FlowPoint } from './overview-animated-flow-line-rendering';

function fallbackSide(normal: THREE.Vector3, target: THREE.Vector3) {
  const axis =
    Math.abs(normal.y) < 0.9
      ? new THREE.Vector3(0, 1, 0)
      : new THREE.Vector3(1, 0, 0);
  return target.crossVectors(normal, axis).normalize();
}

export function createGlobeRouteRibbonGeometry(
  points: readonly FlowPoint[]
): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry();
  if (points.length < 2) return geometry;

  const positions = new Float32Array(points.length * 2 * 3);
  const sides = new Float32Array(points.length * 2 * 3);
  const indices = new Uint32Array((points.length - 1) * 6);

  const previous = new THREE.Vector3();
  const current = new THREE.Vector3();
  const next = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const side = new THREE.Vector3();

  for (let index = 0; index < points.length; index += 1) {
    const point = points[index];
    current.set(point[0], point[1], point[2]);

    if (index === 0) {
      previous
        .copy(current)
        .sub(next.set(points[1][0], points[1][1], points[1][2]).sub(current));
    } else {
      const source = points[index - 1];
      previous.set(source[0], source[1], source[2]);
    }

    if (index === points.length - 1) {
      next.copy(current).add(tangent.copy(current).sub(previous));
    } else {
      const source = points[index + 1];
      next.set(source[0], source[1], source[2]);
    }

    tangent.copy(next).sub(previous).normalize();
    normal.copy(current).normalize();
    side.crossVectors(normal, tangent);

    if (side.lengthSq() < 1e-10) {
      fallbackSide(normal, side);
    } else {
      side.normalize();
    }

    for (let sideIndex = 0; sideIndex < 2; sideIndex += 1) {
      const sign = sideIndex === 0 ? -1 : 1;
      const vertexIndex = index * 2 + sideIndex;
      const offset = vertexIndex * 3;
      positions[offset] = current.x;
      positions[offset + 1] = current.y;
      positions[offset + 2] = current.z;
      sides[offset] = side.x * sign;
      sides[offset + 1] = side.y * sign;
      sides[offset + 2] = side.z * sign;
    }
  }

  for (let index = 0; index < points.length - 1; index += 1) {
    const left = index * 2;
    const right = left + 1;
    const nextLeft = left + 2;
    const nextRight = left + 3;
    const offset = index * 6;

    indices[offset] = left;
    indices[offset + 1] = right;
    indices[offset + 2] = nextLeft;
    indices[offset + 3] = right;
    indices[offset + 4] = nextRight;
    indices[offset + 5] = nextLeft;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSide', new THREE.BufferAttribute(sides, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeBoundingSphere();
  return geometry;
}
