/** @vitest-environment jsdom */
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PerspectiveCamera } from 'three';
import type { ComponentProps } from 'react';
const scene = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  frame: undefined as undefined | ((state: unknown, delta: number) => void),
}));
vi.mock('@react-three/fiber', () => ({
  useThree: (selector: (state: unknown) => unknown) => selector(scene.state),
  useFrame: (frame: typeof scene.frame) => {
    scene.frame = frame;
  },
}));
vi.mock('@react-three/drei', () => ({ OrbitControls: () => null }));
import { OverviewMapController } from './OverviewMapController';
afterEach(cleanup);
function setup() {
  const camera = new PerspectiveCamera(45, 390 / 380);
  camera.position.set(0, 0, 22);
  camera.lookAt(0, 0, 0);
  scene.state = {
    camera,
    size: { width: 390, height: 380 },
    gl: { domElement: document.createElement('canvas') },
  };
  const props: ComponentProps<typeof OverviewMapController> = {
    mode: 'stacked',
    safeRect: { x: 12, y: 12, width: 170, height: 245 },
    exploring: false,
    intent: 'automatic',
    aircraft: { latitude: 35, longitude: -100 },
    followAvailable: true,
    reducedMotion: false,
    route: [],
    initialReady: true,
    resetRevision: 0,
    onManual: vi.fn(),
    onCameraSettled: vi.fn(),
  };
  return { camera, props };
}
it('finishes an ongoing automatic move immediately when reduced motion is selected', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} />);
  scene.frame?.({}, 0.05);
  view.rerender(<OverviewMapController {...props} reducedMotion />);
  scene.frame?.({}, 0.05);
  const stopped = camera.position.clone();
  for (let i = 0; i < 20; i++) scene.frame?.({}, 0.05);
  expect(camera.position.distanceTo(stopped)).toBeLessThan(0.00001);
});
it('cancels an automatic move immediately when manual intent takes over', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} />);
  scene.frame?.({}, 0.05);
  const manual = camera.position.clone();
  view.rerender(<OverviewMapController {...props} intent="manual" />);
  for (let i = 0; i < 20; i++) scene.frame?.({}, 0.05);
  expect(camera.position.distanceTo(manual)).toBeLessThan(0.00001);
});
