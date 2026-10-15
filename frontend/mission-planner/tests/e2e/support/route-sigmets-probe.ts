import type { Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type { BufferGeometry, Material, Object3D, Texture } from 'three';
import type { WeatherBudget } from '../../../src/pages/aviation-weather/weather-budget';

type Probe = Window & {
  __overviewEvidenceRoots?: {
    containerInfo?: { getState?: () => RootState };
  }[];
  __sigmetDisposed?: string[];
  __sigmetBudget?: () => ReturnType<WeatherBudget['snapshot']>;
};
export async function routeSigmetSnapshot(page: Page, watch = false) {
  return page.evaluate((watch) => {
    const target = window as Probe;
    const state = target.__overviewEvidenceRoots
      ?.find((r) => r.containerInfo?.getState?.().gl.domElement.isConnected)
      ?.containerInfo?.getState?.();
    const owner = state?.scene.getObjectByName(
      'Native route SIGMET presentation'
    );
    target.__sigmetDisposed ??= [];
    if (owner) target.__sigmetBudget = owner.userData.routeSigmetBudget;
    const objects: {
      name: string;
      uuid: string;
      vertices: number;
      bytes: number;
      depthTest: boolean[];
      points: number[];
    }[] = [];
    const resources: string[] = [];
    const sharedResources: string[] = [];
    owner?.traverse((node) => {
      const drawable = node as Object3D & {
        geometry?: BufferGeometry;
        material?: Material | Material[];
      };
      const geometry = drawable.geometry;
      const materials = drawable.material
        ? Array.isArray(drawable.material)
          ? drawable.material
          : [drawable.material]
        : [];
      const observe = (resource: BufferGeometry | Material | Texture) => {
        resources.push(resource.uuid);
        if (watch)
          resource.addEventListener('dispose', () =>
            target.__sigmetDisposed!.push(resource.uuid)
          );
      };
      // THREE.Sprite.geometry is the module-wide singleton (_geometry in
      // three/src/objects/Sprite.js). Materials and label textures are owned.
      if (geometry && node.type === 'Sprite')
        sharedResources.push(geometry.uuid);
      else if (geometry) observe(geometry);
      for (const material of materials) {
        observe(material);
        const map = (material as Material & { map?: Texture }).map;
        if (map) observe(map);
      }
      objects.push({
        name: node.name,
        uuid: node.uuid,
        vertices: geometry?.getAttribute('position')?.count ?? 0,
        bytes: geometry
          ? Object.values(geometry.attributes).reduce(
              (n, a) => n + a.array.byteLength,
              geometry.index?.array.byteLength ?? 0
            )
          : 0,
        depthTest: materials.map((m) => m.depthTest),
        points: geometry
          ? Array.from(geometry.getAttribute('position').array).slice(0, 12)
          : [],
      });
    });
    const gl = state?.gl.getContext();
    const extension = gl?.getExtension('WEBGL_debug_renderer_info');
    return {
      present: !!owner,
      objects,
      resources,
      sharedResources,
      disposed: [...target.__sigmetDisposed],
      budget: target.__sigmetBudget?.(),
      calls: state?.gl.info.render.calls ?? 0,
      renderer: gl
        ? String(
            gl.getParameter(
              extension ? extension.UNMASKED_RENDERER_WEBGL : gl.RENDERER
            )
          )
        : null,
      layers: [
        'Native METAR / SPECI observations',
        'Native TAF terminal forecasts',
        'Overview precipitation radar',
      ].map((name) => !!state?.scene.getObjectByName(name)),
    };
  }, watch);
}

export async function setVisibility(page: Page, hidden: boolean) {
  await page.evaluate((hidden) => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      value: hidden,
    });
    document.dispatchEvent(new Event('visibilitychange'));
  }, hidden);
}
