import { describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import {
  CORE_COLOR,
  DEFAULT_GLOW_SIZE_PIXELS,
  createStarMarkerHaloResources,
  disposeStarMarkerHaloResources,
  projectedCoreRadius,
  resolveStarMarkerPosition,
} from './overview-star-marker-rendering';

const viewportHeight = 1_080;
const cameraFovDegrees = 45;

describe('OverviewStarMarker rendering contract', () => {
  it('resolves coordinate and explicit-position marker modes', () => {
    const coordinatePosition = resolveStarMarkerPosition({
      coordinate: { latitude: 0, longitude: 90 },
    });

    expect(coordinatePosition[0]).toBeCloseTo(0);
    expect(coordinatePosition.slice(1)).toEqual([0, -2.02]);
    expect(
      resolveStarMarkerPosition({
        position: [4, 5, 6],
      })
    ).toEqual([4, 5, 6]);
  });

  it('keeps the physical core at or below its configured radius', () => {
    expect(
      projectedCoreRadius({
        configuredRadius: 0.02,
        maxCorePixels: 4,
        distance: 22,
        cameraFovDegrees,
        viewportHeight,
      })
    ).toBe(0.02);
  });

  it('shrinks a close physical core to the projection-aware pixel cap', () => {
    const radius = projectedCoreRadius({
      configuredRadius: 0.02,
      maxCorePixels: 4,
      distance: 3,
      cameraFovDegrees,
      viewportHeight,
    });

    expect(radius).toBeLessThan(0.02);
    expect(radius).toBeCloseTo(
      (4 / 2) * ((2 * 3 * Math.tan((45 * Math.PI) / 180 / 2)) / 1_080)
    );
  });

  it('builds a fixed-pixel, globe-occluded halo material', () => {
    const { geometry, material } = createStarMarkerHaloResources({
      color: '#c084fc',
      glowSizePixels: DEFAULT_GLOW_SIZE_PIXELS,
      glowIntensity: 0.8,
    });

    expect(geometry.getAttribute('position').count).toBe(1);
    expect(material.depthTest).toBe(true);
    expect(material.depthWrite).toBe(false);
    expect(material.transparent).toBe(true);
    expect(material.blending).toBe(THREE.AdditiveBlending);
    expect(material.uniforms.uGlowSizePixels.value).toBe(
      DEFAULT_GLOW_SIZE_PIXELS
    );
    expect(material.uniforms.uColor.value.getStyle()).toBe('rgb(192,132,252)');

    disposeStarMarkerHaloResources({ geometry, material });
  });

  it('disposes renderer-native halo resources on cleanup', () => {
    const resources = createStarMarkerHaloResources({
      color: '#ffb000',
      glowSizePixels: 20,
      glowIntensity: 1,
    });
    const disposeGeometry = vi.spyOn(resources.geometry, 'dispose');
    const disposeMaterial = vi.spyOn(resources.material, 'dispose');

    disposeStarMarkerHaloResources(resources);

    expect(disposeGeometry).toHaveBeenCalledOnce();
    expect(disposeMaterial).toHaveBeenCalledOnce();
  });

  it('uses a tiny white emissive core independent of marker color', () => {
    expect(CORE_COLOR).toBe('#ffffff');
  });
});
