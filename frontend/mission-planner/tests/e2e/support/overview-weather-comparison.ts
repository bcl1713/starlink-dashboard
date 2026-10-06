import type { Page } from '@playwright/test';
import type { RootState } from '@react-three/fiber';
import type { CanvasTexture, Mesh, ShaderMaterial } from 'three';

export type ComparisonPair = {
  key: { z: number; x: number; y: number };
  radarIdentity: string;
  absenceIdentity: string;
  radarURL: string;
  absenceURL: string;
};
export type ComparisonCapture = {
  snapshotIdentity: string;
  opacity: number;
  basePairs: ComparisonPair[];
  detailPairs: ComparisonPair[];
};
type ComparisonState = {
  material: ShaderMaterial;
  shader: string;
  originalUniforms: ShaderMaterial['uniforms'];
  backup: HTMLCanvasElement[];
  originals: CanvasTexture[];
  detail: CanvasTexture[];
  restored?: boolean;
};
type EvidenceWindow = Window & {
  __overviewEvidenceRoots?: Array<{
    containerInfo?: { getState?: () => RootState };
  }>;
  __weatherComparison?: ComparisonState;
  __weatherComparisonMetrics?: {
    fetchMilliseconds: number;
    decodeMilliseconds: number;
    uploadMilliseconds: number;
    pngRequests: number;
    pngBytes: number;
    weatherGPUBytes: number;
    ownedDecodedPeakBytes: number;
  };
};

export async function restoreComparison(page: Page): Promise<void> {
  await page.evaluate(() => {
    const target = window as EvidenceWindow;
    const saved = target.__weatherComparison;
    if (!saved || saved.restored) return;
    saved.restored = true;
    saved.material.fragmentShader = saved.shader;
    for (const name of [
      'comparisonRadar',
      'comparisonAbsence',
      'comparisonBounds',
      'comparisonRects',
      'comparisonOpacity',
    ]) {
      delete saved.originalUniforms[name];
    }
    saved.material.uniforms = saved.originalUniforms;
    saved.originals.forEach((texture, index) => {
      const canvas = texture.image as HTMLCanvasElement;
      const context = canvas.getContext('2d')!;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(saved.backup[index], 0, 0);
      texture.needsUpdate = true;
    });
    saved.detail.forEach((texture) => {
      texture.dispose();
      const canvas = texture.image as HTMLCanvasElement;
      canvas.width = canvas.height = 0;
    });
    saved.backup.forEach((canvas) => (canvas.width = canvas.height = 0));
    saved.material.needsUpdate = true;
    delete target.__weatherComparison;
  });
}

export async function installComparison(
  page: Page,
  capture: ComparisonCapture
): Promise<void> {
  await restoreComparison(page);
  try {
    await page.evaluate(async (input) => {
      const target = window as EvidenceWindow;
      if (
        input.detailPairs.length > 8 ||
        ![0, 16].includes(input.basePairs.length)
      )
        throw new Error(
          'Bounded complete baseline and eight detail pairs required'
        );
      for (const pair of [...input.basePairs, ...input.detailPairs]) {
        if (
          pair.radarIdentity !== input.snapshotIdentity ||
          pair.absenceIdentity !== input.snapshotIdentity
        )
          throw new Error('Mixed frame identities refused');
      }
      const s = target.__overviewEvidenceRoots
        ?.find(
          (root) => root.containerInfo?.getState?.().gl.domElement.isConnected
        )
        ?.containerInfo?.getState?.();
      if (!s) throw new Error('No native renderer');
      const mesh = s.scene.getObjectByName(
        'Overview precipitation radar'
      ) as Mesh;
      const material = mesh.material as ShaderMaterial;
      const originals = [
        material.uniforms.radarTexture.value,
        material.uniforms.coverageTexture.value,
      ] as CanvasTexture[];
      const backup = originals.map((texture) => {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 2048;
        canvas.getContext('2d')!.drawImage(texture.image, 0, 0);
        return canvas;
      });
      const saved: ComparisonState = {
        material,
        shader: material.fragmentShader,
        originalUniforms: material.uniforms,
        backup,
        originals,
        detail: [],
      };
      target.__weatherComparison = saved;
      const metrics = (target.__weatherComparisonMetrics = {
        fetchMilliseconds: 0,
        decodeMilliseconds: 0,
        uploadMilliseconds: 0,
        pngRequests: 0,
        pngBytes: 0,
        weatherGPUBytes: 48 * 1024 ** 2,
        ownedDecodedPeakBytes: 81 * 1024 ** 2,
      });
      const load = async (url: string) => {
        const fetched = performance.now();
        const response = await fetch(url, {
          signal: AbortSignal.timeout(45_000),
        });
        if (!response.ok) throw new Error(`Capture PNG: ${response.status}`);
        const blob = await response.blob();
        metrics.fetchMilliseconds += performance.now() - fetched;
        metrics.pngRequests++;
        metrics.pngBytes += blob.size;
        if (blob.size > 2 * 1024 ** 2) throw new Error('Capture PNG limit');
        const header = new DataView(await blob.slice(0, 24).arrayBuffer());
        if (
          header.byteLength < 24 ||
          header.getUint32(16) !== 512 ||
          header.getUint32(20) !== 512
        )
          throw new Error('Capture dimensions');
        const decoded = performance.now();
        const bitmap = await createImageBitmap(blob);
        metrics.decodeMilliseconds += performance.now() - decoded;
        if (bitmap.width !== 512 || bitmap.height !== 512) {
          bitmap.close();
          throw new Error('Decoded capture dimensions');
        }
        return bitmap;
      };
      const draw = async (
        pair: ComparisonPair,
        canvases: HTMLCanvasElement[],
        x: number,
        y: number,
        detail: boolean
      ) => {
        for (const [index, url] of [pair.radarURL, pair.absenceURL].entries()) {
          const bitmap = await load(url);
          try {
            const context = canvases[index].getContext('2d')!;
            context.clearRect(x, y, 512, 512);
            if (!detail) context.drawImage(bitmap, x, y);
            else {
              context.drawImage(bitmap, x + 1, y + 1, 510, 510);
              context.drawImage(
                canvases[index],
                x + 1,
                y + 1,
                1,
                510,
                x,
                y + 1,
                1,
                510
              );
              context.drawImage(
                canvases[index],
                x + 510,
                y + 1,
                1,
                510,
                x + 511,
                y + 1,
                1,
                510
              );
              context.drawImage(
                canvases[index],
                x,
                y + 1,
                512,
                1,
                x,
                y,
                512,
                1
              );
              context.drawImage(
                canvases[index],
                x,
                y + 510,
                512,
                1,
                x,
                y + 511,
                512,
                1
              );
            }
          } finally {
            bitmap.close();
          }
        }
      };
      const baseCanvases = originals.map(
        (texture) => texture.image as HTMLCanvasElement
      );
      for (const pair of input.basePairs)
        await draw(
          pair,
          baseCanvases,
          pair.key.x * 512,
          pair.key.y * 512,
          false
        );
      originals.forEach((texture) => (texture.needsUpdate = true));
      const bounds = new Float32Array(32),
        rects = new Float32Array(32);
      const Constructor = originals[0].constructor as typeof CanvasTexture;
      const canvases = [0, 1].map(() => {
        const canvas = document.createElement('canvas');
        canvas.width = 2048;
        canvas.height = 1024;
        const texture = new Constructor(canvas);
        texture.flipY = false;
        texture.generateMipmaps = false;
        texture.colorSpace = originals[saved.detail.length].colorSpace;
        texture.minFilter = originals[0].minFilter;
        texture.magFilter = originals[0].magFilter;
        saved.detail.push(texture);
        return canvas;
      });
      for (const [slot, pair] of input.detailPairs.entries()) {
        const n = 2 ** pair.key.z;
        const x = (slot % 4) * 512,
          y = Math.floor(slot / 4) * 512;
        await draw(pair, canvases, x, y, true);
        bounds.set([pair.key.x / n, pair.key.y / n, 1 / n, 1 / n], slot * 4);
        rects.set(
          [(x + 1) / 2048, (y + 1) / 1024, 510 / 2048, 510 / 1024],
          slot * 4
        );
      }
      saved.detail.forEach((texture) => (texture.needsUpdate = true));
      Object.assign(material.uniforms, {
        comparisonRadar: { value: saved.detail[0] },
        comparisonAbsence: { value: saved.detail[1] },
        comparisonBounds: { value: bounds },
        comparisonRects: { value: rects },
        comparisonOpacity: { value: input.opacity },
      });
      material.fragmentShader =
        `
        uniform sampler2D comparisonRadar;
        uniform sampler2D comparisonAbsence;
        uniform vec4 comparisonBounds[8];
        uniform vec4 comparisonRects[8];
        uniform float comparisonOpacity;
        vec4 comparisonSample(sampler2D coarse, sampler2D detail, vec2 uv) {
          for (int i=0; i<8; i++) {
            vec4 b=comparisonBounds[i];
            if (b.z>0.0 && uv.x>=b.x && uv.x<b.x+b.z && uv.y>=b.y && uv.y<b.y+b.w) {
              vec4 r=comparisonRects[i];
              return texture2D(detail,r.xy+(uv-b.xy)/b.zw*r.zw);
            }
          }
          return texture2D(coarse,uv);
        }
      ` +
        saved.shader
          .replace(
            'texture2D(coverageTexture, uv)',
            'comparisonSample(coverageTexture, comparisonAbsence, uv)'
          )
          .replace(
            'texture2D(radarTexture, uv)',
            'comparisonSample(radarTexture, comparisonRadar, uv)'
          )
          .replaceAll('radar.a * 0.72', 'radar.a * comparisonOpacity');
      material.needsUpdate = true;
      const upload = performance.now();
      s.gl.render(s.scene, s.camera);
      s.gl.getContext().finish();
      metrics.uploadMilliseconds = performance.now() - upload;
    }, capture);
  } catch (error) {
    await restoreComparison(page);
    throw error;
  }
}
