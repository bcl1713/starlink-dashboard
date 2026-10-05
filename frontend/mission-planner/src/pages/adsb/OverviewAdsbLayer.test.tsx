/** @vitest-environment jsdom */
import { create, act } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { OverviewAdsbLayer } from './OverviewAdsbLayer';
import { projectAdsbContacts } from './overview-adsb-state';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
it('uses batched depth-tested glyphs, retains buffers between updates and releases resources', async () => {
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
  expect((mesh.material as THREE.MeshBasicMaterial).depthTest).toBe(true);
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
