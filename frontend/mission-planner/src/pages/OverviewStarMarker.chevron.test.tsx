/** @vitest-environment jsdom */
import { create, act } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { StarMarker } from './OverviewStarMarker';

it('keeps a chevron at the same pixel height when the camera zooms and disposes its resources', async () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const view = await create(
    <StarMarker
      position={[0, 0, 2]}
      color="#72b7ff"
      size={0.15}
      shape="chevron"
    />,
    { camera, width: 1000, height: 1000 }
  );
  const meshes = view.scene.findAllByType('Mesh');
  const marker = meshes[0].instance as THREE.Mesh;
  const projectedHeight = () => {
    marker.updateMatrixWorld();
    const top = new THREE.Vector3(0, 1, 0)
      .applyMatrix4(marker.matrixWorld)
      .project(camera);
    const bottom = new THREE.Vector3(0, -1, 0)
      .applyMatrix4(marker.matrixWorld)
      .project(camera);
    return Math.abs(top.y - bottom.y) * 500;
  };
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(meshes).toHaveLength(2);
  expect(projectedHeight()).toBeCloseTo(15, 4);
  camera.position.z = 3;
  camera.updateMatrixWorld();
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(projectedHeight()).toBeCloseTo(15, 4);
  const disposeGeometry = vi.spyOn(marker.geometry, 'dispose');
  const disposeMaterial = vi.spyOn(
    marker.material as THREE.Material,
    'dispose'
  );
  const halo = marker.children[0] as THREE.Mesh;
  const disposeHaloGeometry = vi.spyOn(halo.geometry, 'dispose');
  const disposeHaloMaterial = vi.spyOn(
    halo.material as THREE.Material,
    'dispose'
  );
  await view.unmount();
  expect(disposeHaloGeometry).toHaveBeenCalledOnce();
  expect(disposeHaloMaterial).toHaveBeenCalledOnce();
  expect(disposeGeometry).toHaveBeenCalledOnce();
  expect(disposeMaterial).toHaveBeenCalledOnce();
});

it('hides the own-aircraft chevron behind Earth and restores it when the camera crosses to that side', async () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const view = await create(
    <StarMarker
      position={[0, 0, -2.000001]}
      color="#72b7ff"
      size={0.15}
      shape="chevron"
    />,
    { camera }
  );
  const marker = view.scene.findAllByType('Mesh')[0].instance as THREE.Mesh;
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(marker.visible).toBe(false);
  camera.position.z = -10;
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(marker.visible).toBe(true);
  // The center's visibility gates the complete screen overlay, so Earth cannot slice its wings.
  expect((marker.material as THREE.Material).depthTest).toBe(false);
  await view.unmount();
});

it.each([
  [0, [0, 1, 0]],
  [90, [1, 0, 0]],
  [180, [0, -1, 0]],
  [270, [-1, 0, 0]],
] as const)(
  'projects own-aircraft heading %s rather than keeping the chevron upright',
  async (headingDegrees, expected) => {
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 10);
    camera.lookAt(0, 0, 0);
    const view = await create(
      <StarMarker
        coordinate={{ latitude: 0, longitude: -90 }}
        color="#72b7ff"
        size={0.15}
        shape="chevron"
        headingDegrees={headingDegrees}
      />,
      { camera }
    );
    await act(async () => {
      await view.advanceFrames(1, 0.1);
    });
    const marker = view.scene.findAllByType('Mesh')[0].instance as THREE.Mesh;
    const direction = new THREE.Vector3(0, 1, 0).transformDirection(
      marker.matrix
    );
    expected.forEach((value, index) =>
      expect(direction.getComponent(index)).toBeCloseTo(value, 5)
    );
    await view.unmount();
  }
);

it('scales glow width with aircraft size when tuning the chevron', async () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  const props = {
    position: [0, 0, 2] as [number, number, number],
    color: '#72b7ff',
    size: 0.15,
    shape: 'chevron' as const,
  };
  const view = await create(<StarMarker {...props} chevronSizePixels={15} />, {
    camera,
    width: 1000,
    height: 1000,
  });
  const marker = view.scene.findAllByType('Mesh')[0].instance as THREE.Mesh;
  const halo = marker.children[0] as THREE.Mesh;
  const glowWidth = () => {
    marker.updateMatrixWorld();
    const a = new THREE.Vector3(0, 1, 0)
      .applyMatrix4(marker.matrixWorld)
      .project(camera);
    const b = new THREE.Vector3(0, -1, 0)
      .applyMatrix4(marker.matrixWorld)
      .project(camera);
    const height = Math.abs(a.y - b.y) * 500;
    return (
      ((halo.material as THREE.ShaderMaterial).uniforms.uGlowWidth.value *
        height) /
      2
    );
  };
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(glowWidth()).toBeCloseTo(5, 5);
  const geometry = halo.geometry;
  await view.update(<StarMarker {...props} chevronSizePixels={9} />);
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(glowWidth()).toBeCloseTo(3, 5);
  expect(halo.geometry).toBe(geometry);
  await view.unmount();
});
