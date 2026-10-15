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
        night: boolean,
        radius?: number
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
      type Fiber = {
        memoizedProps?: { work?: { snapshot: () => unknown }; atlas?: unknown };
        child?: Fiber;
        sibling?: Fiber;
      };
      const find = (node: Fiber | undefined): Fiber | undefined => {
        if (!node) return;
        if (node.memoizedProps?.work && node.memoizedProps.atlas) return node;
        return find(node.child) ?? find(node.sibling);
      };
      const owner = (
        target.__overviewEvidenceRoots as unknown as { current?: Fiber }[]
      )
        .map((root) => find(root.current))
        .find(Boolean)?.memoizedProps?.work;
      return {
        work: owner?.snapshot() ?? null,
        canvas:
          s.gl.domElement.dataset.weatherEvidence ??
          (s.gl.domElement.dataset.weatherEvidence = crypto.randomUUID()),
        textures: s.gl.info.memory.textures,
        geometries: s.gl.info.memory.geometries,
        calls: s.gl.info.render.calls,
        radar: radar?.uuid ?? null,
        width: radar?.image.width ?? null,
        detailSlots: [...(material?.uniforms.detailValid.value ?? [])],
        detailFades: [...(material?.uniforms.detailFades.value ?? [])],
        detailBounds: (material?.uniforms.detailBounds.value ?? []).map(
          (value: { toArray(): number[] }) => value.toArray()
        ),
        opacity: material?.uniforms.radarOpacity.value,
        weatherGPUBytes: [
          'radarTexture',
          'coverageTexture',
          'detailRadar',
          'detailCoverage',
        ].reduce((sum, key) => {
          const image = material?.uniforms[key].value?.image;
          return sum + (image ? image.width * image.height * 4 : 0);
        }, 0),
        depthTest: material?.depthTest,
        depthWrite: material?.depthWrite,
        renderOrder: mesh?.renderOrder,
      };
    };
    target.__weatherPixel = (latitude, longitude, night, radius = 5) => {
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
        radius * Math.cos(lat) * Math.cos(lon),
        radius * Math.sin(lat),
        -radius * Math.cos(lat) * Math.sin(lon),
        0,
        0,
        0,
        false
      );
      controls.update(0);
      s.camera.updateMatrixWorld();
      // Overview deliberately offsets its projection around DOM overlays.
      // Sample the independent geographic landmark's projected position,
      // rather than assuming it lies at the viewport center.
      const landmark = s.camera.position
        .clone()
        .set(
          2 * Math.cos(lat) * Math.cos(lon),
          2 * Math.sin(lat),
          -2 * Math.cos(lat) * Math.sin(lon)
        )
        .project(s.camera);
      // Recover the center pixel's geographic ray, including pixel rounding.
      // A sub-texel seam check must know which side was actually rasterized.
      const glContext = s.gl.getContext();
      const pixelX = Math.floor(
        (landmark.x / 2 + 0.5) * glContext.drawingBufferWidth
      );
      const pixelY = Math.floor(
        (landmark.y / 2 + 0.5) * glContext.drawingBufferHeight
      );
      const ray = s.camera.position
        .clone()
        .set(
          ((pixelX + 0.5) / glContext.drawingBufferWidth) * 2 - 1,
          ((pixelY + 0.5) / glContext.drawingBufferHeight) * 2 - 1,
          1
        )
        .unproject(s.camera)
        .sub(s.camera.position)
        .normalize();
      // Intersect the actual tessellated sphere, rather than an ideal sphere:
      // their small depth difference matters for sub-texel seam samples.
      const positions = mesh.geometry.getAttribute('position');
      const indices = mesh.geometry.getIndex()!;
      let nearest = Infinity;
      for (let i = 0; i < indices.count; i += 3) {
        const a = s.camera.position
          .clone()
          .fromBufferAttribute(positions, indices.getX(i));
        const b = s.camera.position
          .clone()
          .fromBufferAttribute(positions, indices.getX(i + 1));
        const c = s.camera.position
          .clone()
          .fromBufferAttribute(positions, indices.getX(i + 2));
        const edge1 = b.sub(a),
          edge2 = c.sub(a);
        const cross = ray.clone().cross(edge2);
        const determinant = edge1.dot(cross);
        if (Math.abs(determinant) < 1e-9) continue;
        const offset = s.camera.position.clone().sub(a);
        const u = offset.dot(cross) / determinant;
        if (u < 0 || u > 1) continue;
        const q = offset.cross(edge1);
        const v = ray.dot(q) / determinant;
        if (v < 0 || u + v > 1) continue;
        const distance = edge2.dot(q) / determinant;
        if (distance > 0) nearest = Math.min(nearest, distance);
      }
      if (!Number.isFinite(nearest))
        throw new Error('Sample misses native weather geometry');
      const point = s.camera.position.clone().addScaledVector(ray, nearest);
      const sampleLongitude = (Math.atan2(-point.z, point.x) * 180) / Math.PI;
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
        const pixels = new Uint8Array(12 * 12 * 4);
        gl.readPixels(
          Math.floor((landmark.x / 2 + 0.5) * gl.drawingBufferWidth) - 6,
          Math.floor((landmark.y / 2 + 0.5) * gl.drawingBufferHeight) - 6,
          12,
          12,
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
      return {
        latitude,
        longitude,
        night,
        sampleLongitude,
        patchWithWeather: withWeather,
        patchWithoutWeather: withoutWeather,
        withWeather: withWeather.slice((6 * 12 + 6) * 4, (6 * 12 + 7) * 4),
        withoutWeather: withoutWeather.slice(
          (6 * 12 + 6) * 4,
          (6 * 12 + 7) * 4
        ),
      };
    };
  });
}
export async function weatherSnapshot(page: Page) {
  await page.waitForFunction(
    () =>
      (
        window as unknown as {
          __overviewEvidenceRoots?: Array<{
            containerInfo?: { getState?: () => RootState };
          }>;
        }
      ).__overviewEvidenceRoots?.some(
        (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
      ),
    null,
    { timeout: 15000 }
  );
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
          work: {
            active: number;
            detailActive: number;
            decodedBytes: number;
            peakDecodedBytes: number;
          } | null;
          detailSlots: number[];
          detailFades: number[];
          detailBounds: number[][];
          opacity: number;
          weatherGPUBytes: number;
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
  night = false,
  radius = 5
) {
  return page.evaluate(
    ([lat, lon, dark, distance]) =>
      (
        window as unknown as {
          __weatherPixel: (
            lat: number,
            lon: number,
            night: boolean,
            radius?: number
          ) => {
            withWeather: number[];
            withoutWeather: number[];
            patchWithWeather: number[];
            patchWithoutWeather: number[];
          };
        }
      ).__weatherPixel(
        lat as number,
        lon as number,
        dark as boolean,
        distance as number
      ),
    [latitude, longitude, night, radius]
  );
}
