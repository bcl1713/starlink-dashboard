/** @vitest-environment jsdom */
import { create } from '@react-three/test-renderer';
import { expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { CityLitGlobe } from '../../pages/CityLitGlobe';
import {
  DEFAULT_EMISSION,
  OverviewBloomMode,
  OverviewBloomEmission,
  OverviewBloomCityIsolation,
} from '../../pages/overview-bloom-mode';
const textures = [new THREE.Texture(), new THREE.Texture()];
vi.mock('@react-three/fiber', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@react-three/fiber')>()),
  useLoader: () => textures,
}));

it('updates compiled city HDR/color/isolation uniforms live without replacing its material', async () => {
  const element = (intensity: number, color: string, isolate = false) => (
    <OverviewBloomMode value={true}>
      <OverviewBloomEmission
        value={{ ...DEFAULT_EMISSION, cities: intensity, cityColor: color }}
      >
        <OverviewBloomCityIsolation value={isolate}>
          <CityLitGlobe sunPosition={[-8, 3, -4]} />
        </OverviewBloomCityIsolation>
      </OverviewBloomEmission>
    </OverviewBloomMode>
  );
  const view = await create(element(20, '#ffb15c'));
  const mesh = view.scene.findByType('Mesh').instance as THREE.Mesh<
    THREE.SphereGeometry,
    THREE.MeshStandardMaterial
  >;
  const material = mesh.material;
  const shader = {
    uniforms: {} as Record<string, { value: unknown }>,
    vertexShader: '#include <beginnormal_vertex>',
    fragmentShader:
      '#include <emissivemap_fragment>\n#include <opaque_fragment>',
  };
  material.onBeforeCompile(
    shader as unknown as Parameters<THREE.Material['onBeforeCompile']>[0],
    {} as THREE.WebGLRenderer
  );
  expect(shader.uniforms.cityEmissionIntensity.value).toBe(20);
  expect(
    (shader.uniforms.cityEmissionColor.value as THREE.Color).getHexString()
  ).toBe('ffb15c');
  await view.update(element(36, '#ff8800', true));
  expect(mesh.material).toBe(material);
  expect(shader.uniforms.cityEmissionIntensity.value).toBe(36);
  expect(
    (shader.uniforms.cityEmissionColor.value as THREE.Color).getHexString()
  ).toBe('ff8800');
  expect(shader.uniforms.citySurfaceScale.value).toBe(0);
  expect(shader.fragmentShader).toContain(
    'outgoingLight = totalEmissiveRadiance'
  );
  await view.unmount();
});
