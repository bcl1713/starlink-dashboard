/** @vitest-environment jsdom */
import { reconciler } from '@react-three/fiber';
import { create, act } from '@react-three/test-renderer';
import { StrictMode } from 'react';
import { expect, it, vi } from 'vitest';
import { OrbitalSprites } from './OrbitalSprites';
import { spriteSnapshot } from './sprite-test-fixtures';
import * as THREE from 'three';

it('motion_and_handover updates uniforms only per frame and reduced motion is static', async () => {
  const current = spriteSnapshot();
  const previous = { ...spriteSnapshot([[6900, 0, 0]]), utcMs: 0 };
  const view = await create(
    <OrbitalSprites
      current={current}
      previous={previous}
      generation={1}
      reducedMotion={false}
    />
  );
  const points = view.scene.findByType('Points').instance as THREE.Points<
    THREE.BufferGeometry,
    THREE.ShaderMaterial
  >;
  const array = points.geometry.getAttribute('position').array;
  await act(async () => {
    await view.advanceFrames(1, 0.5);
  });
  expect(points.material.uniforms.mixAmount.value).toBeCloseTo(0.5);
  expect(points.geometry.getAttribute('position').array).toBe(array);
  await view.update(
    <OrbitalSprites
      current={current}
      previous={previous}
      generation={1}
      reducedMotion
    />
  );
  await act(async () => {
    await view.advanceFrames(1, 0.1);
  });
  expect(points.material.uniforms.mixAmount.value).toBe(1);
  await view.unmount();
});
it('StrictMode creates fresh resources and mid-interpolation disable releases every setup', async () => {
  const geometry = vi.spyOn(THREE.BufferGeometry.prototype, 'dispose');
  const material = vi.spyOn(THREE.ShaderMaterial.prototype, 'dispose');
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  const original = reconciler.createContainer;
  const strictRoot = vi
    .spyOn(reconciler, 'createContainer')
    .mockImplementation((...args) => {
      args[3] = true;
      return original(...args);
    });
  const view = await create(
    <StrictMode>
      <OrbitalSprites
        current={spriteSnapshot()}
        previous={null}
        generation={1}
        reducedMotion={false}
      />
    </StrictMode>
  );
  strictRoot.mockRestore();
  expect(view.scene.findAllByType('Points')).toHaveLength(1);
  await view.update(<StrictMode>{null}</StrictMode>);
  expect(view.scene.findAllByType('Points')).toHaveLength(0);
  expect(geometry).toHaveBeenCalledTimes(2);
  expect(material).toHaveBeenCalledTimes(2);
  await view.unmount();
  vi.restoreAllMocks();
});
