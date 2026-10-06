import * as THREE from 'three';
import type { WeatherAtlasPair } from './weather-atlas';
export type WeatherTextureSet = {
  radar: THREE.CanvasTexture;
  coverage: THREE.CanvasTexture;
};
function texture(canvas: HTMLCanvasElement, colorSpace: THREE.ColorSpace) {
  const value = new THREE.CanvasTexture(canvas);
  value.colorSpace = colorSpace;
  value.flipY = false; // Atlas and shader both use provider top-left Mercator UVs.
  value.generateMipmaps = false;
  value.minFilter = value.magFilter = THREE.LinearFilter;
  value.wrapS = THREE.RepeatWrapping;
  value.wrapT = THREE.ClampToEdgeWrapping;
  return value;
}
export class WeatherTextureOwner {
  private textures: WeatherTextureSet | null = null;
  replace(atlas: WeatherAtlasPair | null): WeatherTextureSet | null {
    if (!atlas) {
      this.dispose();
      return null;
    }
    const old = this.textures;
    const radar =
      old?.radar.image === atlas.radar
        ? old.radar
        : texture(atlas.radar, THREE.SRGBColorSpace);
    // Commit the pending radar before allocating replacement coverage: peak
    // old/new radar + mask OR one radar + old/new mask, never four textures.
    if (old && old.radar !== radar) old.radar.dispose();
    const coverage =
      old?.coverage.image === atlas.coverage
        ? old.coverage
        : texture(atlas.coverage, THREE.NoColorSpace);
    if (old && old.coverage !== coverage) old.coverage.dispose();
    this.textures = { radar, coverage };
    return this.textures;
  }
  dispose() {
    this.textures?.radar.dispose();
    this.textures?.coverage.dispose();
    this.textures = null;
  }
}
