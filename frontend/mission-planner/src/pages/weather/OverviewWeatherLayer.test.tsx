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
it('disposes detail before replacing coarse textures and preserves uniform objects across frame swaps', async () => {
  const { readyWeather } = await import('@/test/weather-fixtures');
  const { WeatherWork } = await import('./weather-work');
  const work = new WeatherWork(),
    context = { generation: 1, settingsRevision: 1, manifest: readyWeather() };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    drawImage: vi.fn(),
    clearRect: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
  const canvas = () => {
    const value = document.createElement('canvas');
    value.width = value.height = 2048;
    return value;
  };
  const atlas = {
    radar: canvas(),
    coverage: canvas(),
    frameTimeMs: 1,
    coverageToken: 1,
    coverageExpiresAtMs: 2,
    dispose: vi.fn(),
  };
  const bitmap = { width: 512, height: 512 } as ImageBitmap;
  const pairs = [
    {
      context,
      key: { z: 5, x: 16, y: 16 },
      radar: bitmap,
      coverage: bitmap,
      dispose: vi.fn(),
    },
  ];
  const order: number[] = [];
  vi.spyOn(THREE.Texture.prototype, 'dispose').mockImplementation(function (
    this: THREE.Texture
  ) {
    const image = this.image as { width: number; height: number };
    order.push(image.width * image.height * 4);
  });
  const view = await create(
    <OverviewWeatherLayer
      atlas={atlas}
      context={context}
      pairs={pairs}
      work={work}
    />
  );
  const material = (view.scene.findByType('Mesh').instance as THREE.Mesh)
    .material as THREE.ShaderMaterial;
  const uniforms = material.uniforms;
  expect(work.snapshot().decodedBytes).toBe(16 * 1024 * 1024);
  expect(material.fragmentShader).toContain('rain.a*0.40');
  await view.update(
    <OverviewWeatherLayer
      atlas={{ ...atlas, radar: canvas() }}
      context={{ ...context, generation: 2 }}
      pairs={[]}
      work={work}
    />
  );
  expect(order.slice(0, 3)).toEqual([
    8 * 1024 * 1024,
    8 * 1024 * 1024,
    16 * 1024 * 1024,
  ]);
  expect(material.uniforms).toBe(uniforms);
  expect(
    material.uniforms.detailValid.value.every((value: number) => value === 0)
  ).toBe(true);
  expect(work.snapshot().decodedBytes).toBe(0);
  await view.unmount();
  vi.restoreAllMocks();
});
