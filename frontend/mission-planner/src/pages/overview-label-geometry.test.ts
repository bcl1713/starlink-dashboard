import { expect, it } from 'vitest';
import * as THREE from 'three';
import {
  projectOverviewAircraftBounds,
  projectOverviewPaths,
} from './overview-label-geometry';

it('protects the rotated rendered halo plus margin across zoom, viewport and glow changes', () => {
  const scene = new THREE.Scene();
  const marker = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.MeshBasicMaterial()
  );
  marker.name = 'overview-own-aircraft';
  const halo = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({ uniforms: { uExtent: { value: 3 } } })
  );
  marker.add(halo);
  scene.add(marker);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  for (const size of [390, 1080])
    for (const zoom of [3, 10])
      for (const angle of [0, Math.PI / 4, Math.PI / 2]) {
        camera.position.set(0, 0, zoom);
        camera.lookAt(0, 0, 0);
        camera.updateMatrixWorld();
        marker.rotation.z = angle;
        marker.scale.setScalar(0.05);
        scene.updateMatrixWorld(true);
        const [bounds] = projectOverviewAircraftBounds(scene, camera, {
          width: size,
          height: size,
        });
        expect(bounds).toBeDefined();
        for (const x of [-3, 3])
          for (const y of [-3, 3]) {
            const p = new THREE.Vector3(x, y, 0)
              .applyMatrix4(marker.matrixWorld)
              .project(camera);
            const px = ((p.x + 1) * size) / 2,
              py = ((1 - p.y) * size) / 2;
            expect(px - bounds.x).toBeGreaterThanOrEqual(7.99);
            expect(bounds.x + bounds.width - px).toBeGreaterThanOrEqual(7.99);
            expect(py - bounds.y).toBeGreaterThanOrEqual(7.99);
            expect(bounds.y + bounds.height - py).toBeGreaterThanOrEqual(7.99);
          }
      }
  marker.visible = false;
  expect(
    projectOverviewAircraftBounds(scene, camera, { width: 700, height: 500 })
  ).toEqual([]);
  marker.geometry.dispose();
  (marker.material as THREE.Material).dispose();
  halo.geometry.dispose();
  (halo.material as THREE.Material).dispose();
});

it('projects displayed operational path segments in canvas CSS pixels', () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const paths = projectOverviewPaths(
    [
      [
        [0, 0, 2],
        [0.2, 0, 2],
      ],
    ],
    camera,
    { width: 700, height: 500 }
  );
  expect(paths).toHaveLength(1);
  expect(paths[0].start).toEqual({ x: 350, y: 250 });
  expect(paths[0].end.x).toBeCloseTo(371.125);
  expect(paths[0].end.y).toBe(250);
});
