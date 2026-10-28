/** @vitest-environment jsdom */
import { create, act } from '@react-three/test-renderer';
import { expect, it } from 'vitest';
import * as THREE from 'three';
import { OverviewBloomMode } from '../../pages/overview-bloom-mode';
import { StarMarker } from '../../pages/OverviewStarMarker';
import { GlobeRouteRibbon } from '../../pages/GlobeRouteRibbon';

it('removes only synthetic star halos in B and restores A in the same scene', async () => {
  const camera = new THREE.PerspectiveCamera();
  camera.position.z = 6;
  const scene = (bloom: boolean) => (
    <OverviewBloomMode value={bloom}>
      <StarMarker position={[0, 0, 2.01]} color="#66aaff" size={0.1} />
    </OverviewBloomMode>
  );
  const view = await create(scene(false), { camera });
  const originalCamera = camera.position.clone();
  expect(view.scene.findAllByType('Points').length).toBeGreaterThan(1);
  await view.update(scene(true));
  expect(view.scene.findAllByType('Points')).toHaveLength(0);
  expect(view.scene.findAllByType('Mesh')).toHaveLength(1);
  expect(camera.position.equals(originalCamera)).toBe(true);
  await view.update(scene(false));
  expect(view.scene.findAllByType('Points').length).toBeGreaterThan(1);
  await view.unmount();
});
it('B keeps the chevron body and far-side visibility but removes its halo', async () => {
  const view = await create(
    <OverviewBloomMode value={true}>
      <StarMarker
        position={[0, 0, -2.01]}
        shape="chevron"
        color="#66aaff"
        size={0.1}
        ownAircraft
      />
    </OverviewBloomMode>
  );
  await act(async () => {
    await view.advanceFrames(1, 0.016);
  });
  const meshes = view.scene.findAllByType('Mesh');
  expect(meshes).toHaveLength(1);
  expect(meshes[0].instance.visible).toBe(false);
  expect(meshes[0].instance.name).toBe('overview-own-aircraft');
  await view.unmount();
});
it('B ribbon retains the depth-tested core, emits HDR, and restores all A layers', async () => {
  const points = [
    [0, 0, 2.01],
    [0.2, 0, 2.01],
    [0.4, 0, 2.01],
  ] as const;
  const scene = (bloom: boolean) => (
    <OverviewBloomMode value={bloom}>
      <GlobeRouteRibbon points={points} />
    </OverviewBloomMode>
  );
  const view = await create(scene(false));
  const group = view.scene.children[0].instance as THREE.Group;
  expect(group.children).toHaveLength(3);
  await view.update(scene(true));
  expect(group.children).toHaveLength(1);
  const material = (group.children[0] as THREE.Mesh)
    .material as THREE.ShaderMaterial;
  expect(material.depthTest).toBe(true);
  expect(material.uniforms.uColor.value.r).toBeGreaterThan(1);
  await view.update(scene(false));
  expect(group.children).toHaveLength(3);
  await view.unmount();
});

it('fixed-step replay preserves the particle pool across mode switches and repeats across wall-clock deltas', async () => {
  const { AnimatedFlowLine } = await import('../../pages/AnimatedFlowLine');
  const { seededRandom } = await import('./contracts');
  const points = [
    [0, 0, 2.01],
    [0.8, 0, 2.01],
  ] as const;
  const forward = {
    enabled: true,
    rate: 30,
    speed: 0.2,
    color: '#ffb000',
    size: 6,
    brightness: 1,
    maxParticles: 16,
  };
  const random = seededRandom(429);
  const element = (bloom: boolean, step: number) => (
    <OverviewBloomMode value={bloom}>
      <AnimatedFlowLine
        points={points}
        forward={forward}
        random={random}
        replayStep={step}
      />
    </OverviewBloomMode>
  );
  const view = await create(element(false, 1 / 60));
  await act(async () => {
    await view.advanceFrames(20, 0.04);
  });
  const particles = view.scene.findAllByType('Points')[0]
    .instance as THREE.Points<THREE.BufferGeometry, THREE.ShaderMaterial>;
  const positions = Array.from(
    particles.geometry.getAttribute('position').array
  );
  const count = particles.geometry.drawRange.count;
  await view.update(element(true, 0));
  await act(async () => {
    await view.advanceFrames(1, 0.2);
  });
  expect(view.scene.findAllByType('Points')[0].instance).toBe(particles);
  expect(particles.geometry.drawRange.count).toBe(count);
  expect(Array.from(particles.geometry.getAttribute('position').array)).toEqual(
    positions
  );
  expect(particles.material.uniforms.uRealBloom.value).toBe(1);
  await view.unmount();
  const replay = await create(
    <AnimatedFlowLine
      points={points}
      forward={forward}
      random={seededRandom(429)}
      replayStep={1 / 60}
    />
  );
  await act(async () => {
    await replay.advanceFrames(20, 0.007);
  });
  const again = replay.scene.findAllByType('Points')[0]
    .instance as THREE.Points;
  expect(Array.from(again.geometry.getAttribute('position').array)).toEqual(
    positions
  );
  expect(again.geometry.drawRange.count).toBe(count);
  await replay.unmount();
});
