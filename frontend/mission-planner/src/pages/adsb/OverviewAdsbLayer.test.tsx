/** @vitest-environment jsdom */
import { create, act } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import CameraControls from 'camera-controls';
import { OverviewAdsbLayer } from './OverviewAdsbLayer';
import { projectAdsbContacts } from './overview-adsb-state';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
it('uses batched overlay glyphs, retains buffers between updates and releases resources', async () => {
  const contacts = projectAdsbContacts(
    [adsbContact({ latitude: 0, longitude: -90 })],
    adsbSettings(),
    ADSB_NOW
  );
  const occluder = { current: new THREE.Group() };
  const visible = vi.fn();
  const geometry = vi.spyOn(THREE.BufferGeometry.prototype, 'dispose');
  const material = vi.spyOn(THREE.MeshBasicMaterial.prototype, 'dispose');
  const props = {
    contacts,
    globeOccluder: occluder,
    onSelect: vi.fn(),
    onVisibleHexesChange: visible,
  };
  const view = await create(<OverviewAdsbLayer {...props} />);
  const mesh = view.scene
    .findAllByType('Mesh')
    .map((node) => node.instance)
    .find(
      (node) => node instanceof THREE.InstancedMesh && node.count > 0
    ) as THREE.InstancedMesh;
  expect(mesh.count).toBe(1);
  expect((mesh.material as THREE.MeshBasicMaterial).depthTest).toBe(false);
  const buffer = mesh.instanceMatrix.array;
  await view.update(<OverviewAdsbLayer {...props} />);
  await act(async () => {
    await view.advanceFrames(2, 0.1);
  });
  expect(mesh.instanceMatrix.array).toBe(buffer);
  await view.unmount();
  expect(geometry).toHaveBeenCalled();
  expect(material).toHaveBeenCalled();
  vi.restoreAllMocks();
});

it('resizes batched chevrons with camera zoom without replacing their buffers', async () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const view = await create(
    <OverviewAdsbLayer
      contacts={projectAdsbContacts(
        [adsbContact({ latitude: 0, longitude: -90, track_degrees: 0 })],
        adsbSettings(),
        ADSB_NOW
      )}
      globeOccluder={{ current: new THREE.Group() }}
      onSelect={vi.fn()}
      onVisibleHexesChange={vi.fn()}
    />,
    { camera, width: 1000, height: 1000 }
  );
  const mesh = view.scene
    .findAllByType('Mesh')
    .map((n) => n.instance)
    .find(
      (n) => n instanceof THREE.InstancedMesh && n.count > 0
    ) as THREE.InstancedMesh;
  const buffer = mesh.instanceMatrix.array;
  const pixelHeight = () => {
    const matrix = new THREE.Matrix4();
    mesh.getMatrixAt(0, matrix);
    const top = new THREE.Vector3(0, 1, 0).applyMatrix4(matrix).project(camera);
    const bottom = new THREE.Vector3(0, -1, 0)
      .applyMatrix4(matrix)
      .project(camera);
    return Math.abs(top.y - bottom.y) * 500;
  };
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(pixelHeight()).toBeCloseTo(14, 4);
  CameraControls.install({ THREE });
  const controls = new CameraControls(camera);
  await controls.setLookAt(3, 0, 4, 0, 0, 0, false);
  controls.update(1 / 60);
  // Controls mutate position/quaternion before rendering refreshes matrixWorld.
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  camera.updateMatrixWorld();
  expect(pixelHeight()).toBeCloseTo(14, 4);
  controls.dispose();
  expect(mesh.instanceMatrix.array).toBe(buffer);
  await view.unmount();
});

it('zero-scales rear-side instances and restores their chevrons when the camera moves around Earth', async () => {
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const view = await create(
    <OverviewAdsbLayer
      contacts={projectAdsbContacts(
        [adsbContact({ latitude: 0, longitude: 90 })],
        adsbSettings(),
        ADSB_NOW
      )}
      globeOccluder={{ current: new THREE.Group() }}
      onSelect={vi.fn()}
      onVisibleHexesChange={vi.fn()}
    />,
    { camera }
  );
  const mesh = view.scene
    .findAllByType('Mesh')
    .map((n) => n.instance)
    .find(
      (n) => n instanceof THREE.InstancedMesh && n.count > 0
    ) as THREE.InstancedMesh;
  const scale = () =>
    new THREE.Vector3().setFromMatrixScale(
      new THREE.Matrix4().fromArray(mesh.instanceMatrix.array)
    );
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(scale().length()).toBe(0);
  camera.position.z = -10;
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(scale().length()).toBeGreaterThan(0);
  await view.unmount();
});
