/** @vitest-environment jsdom */
import { create } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { OverviewWeatherLayer } from './OverviewWeatherLayer';
it('keeps weather behind route overlays with depth testing and no pointer hits', async () => {
  const radar = document.createElement('canvas');
  const coverage = document.createElement('canvas');
  radar.width = radar.height = coverage.width = coverage.height = 2048;
  const pair = {
    radar,
    coverage,
    frameTimeMs: 1,
    coverageToken: 1,
    coverageExpiresAtMs: 2,
    dispose: vi.fn(),
  };
  const textureDispose = vi.spyOn(THREE.Texture.prototype, 'dispose');
  const view = await create(<OverviewWeatherLayer atlas={pair} />);
  const mesh = view.scene.findByType('Mesh').instance as THREE.Mesh;
  const material = mesh.material as THREE.ShaderMaterial;
  expect(material.depthTest).toBe(true);
  expect(material.depthWrite).toBe(false);
  expect(material.transparent).toBe(true);
  expect(material.toneMapped).toBe(false);
  expect(mesh.renderOrder).toBeLessThan(0);
  const intersections: THREE.Intersection[] = [];
  mesh.raycast(new THREE.Raycaster(), intersections);
  expect(intersections).toEqual([]);
  expect(material.uniforms.radarTexture.value.image).toBe(radar);
  await view.unmount();
  expect(textureDispose).toHaveBeenCalledTimes(2);
  expect(pair.dispose).not.toHaveBeenCalled();
  vi.restoreAllMocks();
});
