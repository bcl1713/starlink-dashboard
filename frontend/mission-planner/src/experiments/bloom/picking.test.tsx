/** @vitest-environment jsdom */
import { create, act } from '@react-three/test-renderer';
import { expect, it } from 'vitest';
import * as THREE from 'three';
import { StarMarker } from '../../pages/OverviewStarMarker';
import { OverviewBloomMode } from '../../pages/overview-bloom-mode';

const width = 1000,
  height = 800;
const markers = [
  { id: 'solo', position: [0.6, -0.3, 1.9] },
  { id: 'overlap-a', position: [0, 0, 2.006] },
  { id: 'overlap-b', position: [0.012, 0.01, 2.006] },
  { id: 'far', position: [-0.6, 0.4, -1.9] },
] as const;
it('real raycasts select identical center/offset/overlap targets in A/B/A and exclude far-side POIs', async () => {
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
  camera.position.set(0, 0, 6);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  const element = (bloom: boolean) => (
    <OverviewBloomMode value={bloom}>
      <group name="pick-scene">
        {markers.map((marker) => (
          <group key={marker.id} name={marker.id}>
            <StarMarker
              position={[...marker.position]}
              color="#66aaff"
              size={0.1}
              pickRadiusPixels={12}
            />
          </group>
        ))}
      </group>
    </OverviewBloomMode>
  );
  const view = await create(element(false), { camera, width, height });
  const target = markers[0];
  const pixels = (position: readonly number[], dx = 0) => {
    const p = new THREE.Vector3(...position).project(camera);
    return new THREE.Vector2(p.x + (dx * 2) / width, p.y);
  };
  const raycaster = new THREE.Raycaster();
  const picks = (point: THREE.Vector2) => {
    const group = view.scene.findByProps({ name: 'pick-scene' })
      .instance as THREE.Group;
    group.updateMatrixWorld(true);
    raycaster.setFromCamera(point, camera);
    return raycaster.intersectObject(group, true).map((hit) => {
      let node: THREE.Object3D | null = hit.object;
      while (node && !markers.some((marker) => marker.id === node?.name))
        node = node.parent;
      return node?.name;
    });
  };
  const selections: string[][] = [];
  for (const bloom of [false, true, false]) {
    await view.update(element(bloom));
    await act(async () => {
      await view.advanceFrames(1, 1 / 60);
    });
    const center = picks(pixels(target.position));
    const offset = picks(pixels(target.position, 8));
    const overlap = picks(pixels(markers[1].position));
    expect(center[0]).toBe('solo');
    expect(offset[0]).toBe('solo');
    expect(picks(pixels(target.position, 16))).toEqual([]);
    expect(new Set(overlap)).toEqual(new Set(['overlap-a', 'overlap-b']));
    expect(picks(pixels(markers[3].position))).toEqual([]);
    selections.push([center[0]!, offset[0]!, ...overlap] as string[]);
  }
  expect(selections[1]).toEqual(selections[0]);
  expect(selections[2]).toEqual(selections[0]);
  await view.unmount();
});
