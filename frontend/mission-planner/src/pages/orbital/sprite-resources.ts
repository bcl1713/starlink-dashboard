import * as THREE from 'three';
import { ecefKmToScene } from './coordinates';
import { pointAt, physicalEndpoint } from './geometry';
import { MAX_OBJECTS, type OrbitalSnapshot } from './types';

export interface SpriteResources {
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
  points: THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  capacity: number;
  disposed: boolean;
}
export function createSpriteResources(capacity: number): SpriteResources {
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > MAX_OBJECTS)
    throw new Error('Invalid orbital sprite capacity');
  const geometry = new THREE.BufferGeometry();
  for (const name of ['position', 'previous'])
    geometry.setAttribute(
      name,
      new THREE.BufferAttribute(new Float32Array(capacity * 3), 3).setUsage(
        THREE.DynamicDrawUsage
      )
    );
  geometry.setAttribute(
    'eligible',
    new THREE.BufferAttribute(new Float32Array(capacity), 1).setUsage(
      THREE.DynamicDrawUsage
    )
  );
  geometry.setDrawRange(0, 0);
  const material = new THREE.ShaderMaterial({
    uniforms: { mixAmount: { value: 1 } },
    vertexShader: `
      attribute vec3 previous;
      attribute float eligible;
      uniform float mixAmount;
      varying float visibleDot;
      void main() {
        visibleDot = eligible;
        vec3 p = mix(previous, position, mixAmount);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = 3.0;
        if (eligible < 0.5) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
      }`,
    fragmentShader: `
      varying float visibleDot;
      void main() {
        float radius = length(gl_PointCoord - vec2(0.5));
        if (visibleDot < 0.5 || radius > 0.5) discard;
        gl_FragColor = vec4(0.65, 0.72, 0.82, 0.55 * (1.0 - smoothstep(0.2, 0.5, radius)));
      }`,
    depthTest: true,
    depthWrite: false,
    transparent: true,
    toneMapped: false,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  return { geometry, material, points, capacity, disposed: false };
}
export function disposeSpriteResources(resources: SpriteResources) {
  if (resources.disposed) return;
  resources.disposed = true;
  resources.geometry.dispose();
  resources.material.dispose();
}
/** Copy once per snapshot; the worker owns physical banks, the renderer owns GPU arrays. */
export function writeSpriteSnapshots(
  resources: SpriteResources,
  previous: OrbitalSnapshot | null,
  current: OrbitalSnapshot | null,
  generation: number
): number {
  const { geometry } = resources;
  if (!current || current.generation !== generation || resources.disposed) {
    geometry.setDrawRange(0, 0);
    return 0;
  }
  const old =
    previous?.catalogGeneration === current.catalogGeneration &&
    previous.generation === generation
      ? previous
      : null;
  const oldIndices = new Map(old?.ids.map((id, i) => [id, i]));
  const position = geometry.getAttribute('position') as THREE.BufferAttribute;
  const from = geometry.getAttribute('previous') as THREE.BufferAttribute;
  const eligible = geometry.getAttribute('eligible') as THREE.BufferAttribute;
  let count = 0;
  const size = Math.min(current.ids.length, resources.capacity);
  for (let i = 0; i < size; i++) {
    const point = pointAt(current, i);
    if (!current.valid[i] || !physicalEndpoint(point)) {
      eligible.setX(i, 0);
      position.setXYZ(i, 0, 0, 0);
      from.setXYZ(i, 0, 0, 0);
      continue;
    }
    const index = oldIndices.get(current.ids[i]);
    const prior =
      old && index !== undefined && old.valid[index]
        ? pointAt(old, index)
        : point;
    const safePrior = physicalEndpoint(prior) ? prior : point;
    position.setXYZ(i, ...ecefKmToScene(point));
    from.setXYZ(i, ...ecefKmToScene(safePrior));
    eligible.setX(i, 1);
    count++;
  }
  for (const attribute of [position, from, eligible])
    attribute.needsUpdate = true;
  geometry.setDrawRange(0, size);
  return count;
}
