import { describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import {
  ROUTE_OVERLAY_ALTITUDE_FEET,
  ROUTE_OVERLAY_RADIUS,
} from './globe-render-radii';
import {
  CORE_COLOR,
  DEFAULT_GLOW_SIZE_PIXELS,
  createStarMarkerHaloResources,
  disposeStarMarkerHaloResources,
  projectedCoreRadius,
  resolveStarMarkerPosition,
  setStarMarkerHaloPixelRatio,
} from './overview-star-marker-rendering';

const viewportHeight = 1_080;
const cameraFovDegrees = 45;

describe('OverviewStarMarker rendering contract', () => {
  it('resolves coordinate markers at the ten-foot route overlay radius', () => {
    const coordinatePosition = resolveStarMarkerPosition({
      coordinate: { latitude: 0, longitude: 90 },
    });

    expect(ROUTE_OVERLAY_ALTITUDE_FEET).toBe(10);
    expect(ROUTE_OVERLAY_RADIUS).toBeGreaterThan(2);
    expect(ROUTE_OVERLAY_RADIUS).toBeLessThan(2.00001);
    expect(coordinatePosition[0]).toBeCloseTo(0);
    expect(coordinatePosition[1]).toBeCloseTo(0);
    expect(coordinatePosition[2]).toBeCloseTo(-ROUTE_OVERLAY_RADIUS, 12);
    expect(
      resolveStarMarkerPosition({
        position: [4, 5, 6],
      })
    ).toEqual([4, 5, 6]);
  });

  it('keeps the physical core at or below its configured radius', () => {
    expect(
      projectedCoreRadius({
        configuredRadius: 0.012,
        maxCorePixels: 3,
        distance: 22,
        cameraFovDegrees,
        viewportHeight,
      })
    ).toBe(0.012);
  });

  it('shrinks a close physical core to the projection-aware pixel cap', () => {
    const radius = projectedCoreRadius({
      configuredRadius: 0.012,
      maxCorePixels: 3,
      distance: 3,
      cameraFovDegrees,
      viewportHeight,
    });

    expect(radius).toBeLessThan(0.012);
    expect(radius).toBeCloseTo(
      (3 / 2) * ((2 * 3 * Math.tan((45 * Math.PI) / 180 / 2)) / 1_080)
    );
  });

  it('builds four fixed-pixel, globe-occluded halo layers', () => {
    const resources = createStarMarkerHaloResources({
      color: '#c084fc',
      glowSizePixels: DEFAULT_GLOW_SIZE_PIXELS,
      glowIntensity: 1,
    });

    expect(resources.geometry.getAttribute('position').count).toBe(1);
    expect(resources.layers).toHaveLength(4);
    expect(
      resources.layers.map(
        (layer) => layer.material.uniforms.uSizePixels.value
      )
    ).toEqual([34, 18, 9, 3]);

    for (const layer of resources.layers) {
      expect(layer.material.depthTest).toBe(true);
      expect(layer.material.depthWrite).toBe(false);
      expect(layer.material.transparent).toBe(true);
      expect(layer.material.blending).toBe(THREE.AdditiveBlending);
      expect(layer.material.toneMapped).toBe(false);
      expect(layer.material.uniforms.uDepthBias.value).toBeGreaterThan(0);
    }

    expect(resources.layers[0].material.uniforms.uColor.value.getStyle()).toBe(
      'rgb(192,132,252)'
    );
    expect(resources.layers[3].material.uniforms.uColor.value.getStyle()).toBe(
      'rgb(255,255,255)'
    );

    disposeStarMarkerHaloResources(resources);
  });

  it('updates pixel ratio across every halo layer', () => {
    const resources = createStarMarkerHaloResources({
      color: '#ffb000',
      glowSizePixels: 34,
      glowIntensity: 1,
    });

    setStarMarkerHaloPixelRatio(resources, 2);

    expect(
      resources.layers.every(
        (layer) => layer.material.uniforms.uPixelRatio.value === 2
      )
    ).toBe(true);
    disposeStarMarkerHaloResources(resources);
  });

  it('disposes shared geometry and every halo material on cleanup', () => {
    const resources = createStarMarkerHaloResources({
      color: '#ffb000',
      glowSizePixels: 34,
      glowIntensity: 1,
    });
    const disposeGeometry = vi.spyOn(resources.geometry, 'dispose');
    const disposeMaterials = resources.layers.map((layer) =>
      vi.spyOn(layer.material, 'dispose')
    );

    disposeStarMarkerHaloResources(resources);

    expect(disposeGeometry).toHaveBeenCalledOnce();
    for (const disposeMaterial of disposeMaterials) {
      expect(disposeMaterial).toHaveBeenCalledOnce();
    }
  });

  it('uses a tiny white emissive core independent of marker color', () => {
    expect(CORE_COLOR).toBe('#ffffff');
  });
});
