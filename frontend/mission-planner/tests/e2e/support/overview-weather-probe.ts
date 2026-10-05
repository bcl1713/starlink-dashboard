import type { Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type { Mesh, ShaderMaterial, CanvasTexture, Light } from 'three';
import { observeOverviewCamera } from './overview-camera';

export async function installWeatherProbe(page: Page) {
  await observeOverviewCamera(page);
  await page.addInitScript(() => {
    const target = window as unknown as {
      __overviewEvidenceRoots?: Array<{
        containerInfo?: { getState?: () => RootState };
      }>;
      __weatherSnapshot?: () => unknown;
      __weatherPixel?: (
        latitude: number,
        longitude: number,
        night: boolean
      ) => unknown;
    };
    const state = () => {
      const store = target.__overviewEvidenceRoots?.find(
        (root) =>
          root.containerInfo?.getState &&
          root.containerInfo.getState().gl.domElement.isConnected
      )?.containerInfo;
      if (!store?.getState) throw new Error('No mounted renderer');
      return store.getState();
    };
    target.__weatherSnapshot = () => {
      const s = state();
      const mesh = s.scene.getObjectByName('Overview precipitation radar') as
        | Mesh
        | undefined;
      const material = mesh?.material as ShaderMaterial | undefined;
      const radar = material?.uniforms.radarTexture.value as
        | CanvasTexture
        | undefined;
      return {
        canvas:
          s.gl.domElement.dataset.weatherEvidence ??
          (s.gl.domElement.dataset.weatherEvidence = crypto.randomUUID()),
        textures: s.gl.info.memory.textures,
        geometries: s.gl.info.memory.geometries,
        calls: s.gl.info.render.calls,
        radar: radar?.uuid ?? null,
        width: radar?.image.width ?? null,
        depthTest: material?.depthTest,
        depthWrite: material?.depthWrite,
        renderOrder: mesh?.renderOrder,
      };
    };
    target.__weatherPixel = (latitude, longitude, night) => {
      const s = state();
      const mesh = s.scene.getObjectByName(
        'Overview precipitation radar'
      ) as Mesh;
      if (!mesh) throw new Error('No weather mesh');
      const lat = (latitude * Math.PI) / 180,
        lon = (longitude * Math.PI) / 180;
      const controls = s.controls as unknown as {
        setLookAt: (...values: (number | boolean)[]) => void;
        update: (delta: number) => void;
      };
      controls.setLookAt(
        5 * Math.cos(lat) * Math.cos(lon),
        5 * Math.sin(lat),
        -5 * Math.cos(lat) * Math.sin(lon),
        0,
        0,
        0,
        false
      );
      controls.update(0);
      s.camera.updateMatrixWorld();
      const lights: Array<{ light: Light; intensity: number }> = [];
      if (night)
        s.scene.traverse((node) => {
          if ((node as Light).isLight) {
            const light = node as Light;
            lights.push({ light, intensity: light.intensity });
            light.intensity = 0;
          }
        });
      const read = () => {
        s.gl.render(s.scene, s.camera);
        const gl = s.gl.getContext();
        const pixels = new Uint8Array(4);
        gl.readPixels(
          Math.floor(gl.drawingBufferWidth / 2),
          Math.floor(gl.drawingBufferHeight / 2),
          1,
          1,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          pixels
        );
        return [...pixels];
      };
      const withWeather = read();
      mesh.visible = false;
      const withoutWeather = read();
      mesh.visible = true;
      lights.forEach(({ light, intensity }) => {
        light.intensity = intensity;
      });
      s.gl.render(s.scene, s.camera);
      return { latitude, longitude, night, withWeather, withoutWeather };
    };
  });
}
export async function weatherSnapshot(page: Page) {
  return page.evaluate(() =>
    (
      window as unknown as {
        __weatherSnapshot: () => {
          canvas: string;
          textures: number;
          geometries: number;
          calls: number;
          radar: string | null;
          width: number | null;
          depthTest?: boolean;
          depthWrite?: boolean;
          renderOrder?: number;
        };
      }
    ).__weatherSnapshot()
  );
}
export async function weatherPixel(
  page: Page,
  latitude: number,
  longitude: number,
  night = false
) {
  return page.evaluate(
    ([lat, lon, dark]) =>
      (
        window as unknown as {
          __weatherPixel: (
            lat: number,
            lon: number,
            night: boolean
          ) => { withWeather: number[]; withoutWeather: number[] };
        }
      ).__weatherPixel(lat as number, lon as number, dark as boolean),
    [latitude, longitude, night]
  );
}
