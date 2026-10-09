import { describe, expect, it } from 'vitest';
import { PerspectiveCamera, Vector3 } from 'three';
import { readFileSync } from 'node:fs';
import type { MissionMapInput } from './protocol';
// Read at test runtime: the existing frontend-only production build must not
// resolve backend fixtures while type-checking this test module.
const fixture: { legs: MissionMapInput[]; expectedViewIds: string[] } =
  JSON.parse(
    readFileSync(
      new URL(
        '../../../../backend/starlink-location/tests/fixtures/customer_briefing/f08_map_inputs.json',
        import.meta.url
      ),
      'utf8'
    )
  );
import { frameMissionRoute, applyCameraFrame } from './framing';
import { validateMapInput } from './protocol';

// Breaks caught: cropped/occluded geometry, dropped/reordered segments, wrong
// dateline projection, marker loss, non-deterministic framing, unsafe inputs.
describe('mission map framing', () => {
  it('covers ordered short, polar/dateline and non-hemisphere geometry with shared endpoints', () => {
    const allIds: string[] = [];
    for (const raw of fixture.legs) {
      const input = validateMapInput(raw);
      const views = frameMissionRoute(input);
      allIds.push(...views.map((view) => view.id));
      expect(frameMissionRoute(input)).toEqual(views);
      let expectedStart = 0;
      for (const view of views) {
        expect(view.startIndex).toBe(expectedStart);
        expectedStart = view.endIndex;
        const camera = new PerspectiveCamera(38, 1920 / 1080, 0.1, 100);
        applyCameraFrame(camera, view);
        for (const tuple of view.points) {
          const point = new Vector3(...tuple);
          // Independent visibility inequality: tangent to radius-two Earth.
          expect(point.dot(camera.position)).toBeGreaterThan(4.04);
          const pixel = point.clone().project(camera);
          expect(Math.abs(pixel.x)).toBeLessThan(0.94);
          expect(Math.abs(pixel.y)).toBeLessThan(0.9);
        }
      }
      expect(views[0].startIndex).toBe(0);
      expect(views.at(-1)!.endIndex).toBe(input.route.length * 32 - 32);
      if (input.legId === 'f08-polar-dateline') {
        expect(views).toHaveLength(1);
        expect(views[0].points.every((p) => p[0] < 0)).toBe(true);
      }
      if (input.legId === 'f08-spanning') {
        expect(views.length).toBeGreaterThanOrEqual(2);
        for (let i = 1; i < views.length; i++)
          expect(views[i].points[0]).toEqual(views[i - 1].points.at(-1));
      }
    }
    expect(allIds).toEqual(fixture.expectedViewIds);
  });

  it('uses the map height for a polar route while leaving room for endpoint stars', () => {
    const [view] = frameMissionRoute(validateMapInput(fixture.legs[1]));
    const camera = new PerspectiveCamera(38, 1920 / 1080, 0.1, 100);
    applyCameraFrame(camera, view);
    const ys = view.points.map((p) => new Vector3(...p).project(camera).y);
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(1.5);
  });

  it.each([1920, 2400])(
    'fits the whole route to a %s-pixel tall PDF corner',
    (height) => {
      const viewport = { width: 1920, height };
      const [view] = frameMissionRoute(
        validateMapInput(fixture.legs[1]),
        viewport
      );
      const camera = new PerspectiveCamera(38, 1920 / 1080, 0.1, 100);
      applyCameraFrame(camera, view);
      expect(camera.aspect).toBe(viewport.width / viewport.height);
      expect(view.width).toBe(viewport.width);
      expect(view.height).toBe(viewport.height);
      for (const tuple of view.points) {
        const point = new Vector3(...tuple);
        expect(point.dot(camera.position)).toBeGreaterThan(4.04);
        const projected = point.clone().project(camera);
        const x = ((projected.x + 1) * viewport.width) / 2;
        const y = ((1 - projected.y) * viewport.height) / 2;
        expect(x).toBeGreaterThan(64);
        expect(x).toBeLessThan(viewport.width - 64);
        expect(y).toBeGreaterThan(64);
        expect(y).toBeLessThan(viewport.height - 64);
      }
    }
  );

  it('keeps meaningful endpoint labels through validation and framing', () => {
    const endpointLabels = { departure: 'KADW', arrival: 'PAED' };
    const input = validateMapInput({
      ...fixture.legs[0],
      endpointLabels,
      markers: [],
    });
    const [view] = frameMissionRoute(input);
    expect(view).toHaveProperty('endpointLabels', endpointLabels);
  });

  it('fits synthetic numbered route markers within the padded view', () => {
    const input = validateMapInput({
      ...fixture.legs[0],
      markers: [
        { id: 'synthetic-1', label: '1', routeIndex: 0 },
        { id: 'synthetic-2', label: '2', routeIndex: 1 },
      ],
    });
    const [view] = frameMissionRoute(input);
    expect(view.markers.map((m) => m.id)).toEqual([
      'synthetic-1',
      'synthetic-2',
    ]);
  });

  it.each([
    { ...fixture.legs[0], route: [] },
    { ...fixture.legs[0], referenceUtc: 'bad' },
    {
      ...fixture.legs[0],
      route: [
        { latitude: 91, longitude: 0 },
        { latitude: 0, longitude: 0 },
      ],
    },
    {
      ...fixture.legs[0],
      markers: [{ id: 'bad', label: '1', routeIndex: 99 }],
    },
  ])('rejects malformed data rather than reporting ready', (raw) => {
    expect(() => validateMapInput(raw)).toThrow();
  });
});
