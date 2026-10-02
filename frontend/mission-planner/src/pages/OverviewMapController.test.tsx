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
import { globePosition } from './globe-coordinates';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
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
it('eases into a recovered route once, then ignores aircraft updates and equivalent route samples', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} />);
  const settle = (count: number) => {
    for (
      let i = 0;
      i < 2000 && vi.mocked(props.onCameraSettled).mock.calls.length < count;
      i++
    )
      scene.frame?.({}, 0.05);
    expect(props.onCameraSettled).toHaveBeenCalledTimes(count);
  };
  settle(1);
  const fallback = camera.position.clone();
  const route = [
    [-25, 80],
    [-20, 100],
  ].map(([lat, lon]) => globePosition(lat, lon, 2));
  view.rerender(<OverviewMapController {...props} route={route} />);
  expect(camera.position.distanceTo(fallback)).toBeLessThan(0.00001);
  scene.frame?.({}, 0.05);
  const intermediate = camera.position.clone();
  settle(2);
  const recovered = camera.position.clone();
  expect(recovered.distanceTo(fallback)).toBeGreaterThan(1);
  expect(intermediate.distanceTo(fallback)).toBeGreaterThan(0);
  expect(intermediate.distanceTo(fallback)).toBeLessThan(
    recovered.distanceTo(fallback) * 0.1
  );
  view.rerender(
    <OverviewMapController
      {...props}
      aircraft={{ latitude: 60, longitude: -10 }}
      route={route.map((point) => [...point])}
    />
  );
  for (let i = 0; i < 20; i++) scene.frame?.({}, 0.05);
  expect(camera.position.distanceTo(recovered)).toBeLessThan(0.00001);
});
it('keeps a manual pose when route data recovers', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} intent="manual" />);
  const manual = camera.position.clone();
  view.rerender(
    <OverviewMapController
      {...props}
      intent="manual"
      route={[globePosition(-25, 80, 2), globePosition(-20, 100, 2)]}
    />
  );
  for (let i = 0; i < 20; i++) scene.frame?.({}, 0.05);
  expect(camera.position.distanceTo(manual)).toBeLessThan(0.00001);
});
it.each([30, 60, 144])(
  'limits automatic rotation and zoom speed and acceleration at %i fps',
  (fps) => {
    const { camera, props } = setup();
    render(<OverviewMapController {...props} />);
    const dt = 1 / fps;
    let rotation = camera.quaternion.clone();
    let zoom = Math.log(camera.position.length() - 2);
    let angularSpeed = 0,
      zoomSpeed = 0;
    for (let i = 0; i < fps * 30; i++) {
      scene.frame?.({}, dt);
      const nextAngularSpeed = rotation.angleTo(camera.quaternion) / dt;
      const nextZoom = Math.log(camera.position.length() - 2);
      const nextZoomSpeed = Math.abs(nextZoom - zoom) / dt;
      expect(nextAngularSpeed).toBeLessThanOrEqual(
        (10 * Math.PI) / 180 + 0.00001
      );
      expect(nextZoomSpeed).toBeLessThanOrEqual(0.5 + 0.00001);
      expect(
        Math.abs(nextAngularSpeed - angularSpeed) / dt
      ).toBeLessThanOrEqual((2 * Math.PI) / 180 + 0.001);
      expect(Math.abs(nextZoomSpeed - zoomSpeed) / dt).toBeLessThanOrEqual(
        0.15 + 0.00001
      );
      rotation = camera.quaternion.clone();
      zoom = nextZoom;
      angularSpeed = nextAngularSpeed;
      zoomSpeed = nextZoomSpeed;
    }
    expect(props.onCameraSettled).toHaveBeenCalledTimes(1);
    expect(angularSpeed).toBe(0);
    expect(zoomSpeed).toBe(0);
  }
);

it.each([5, 10, 15, 30, 60, 144])(
  'reaches the same pose after four seconds at %i fps',
  (fps) => {
    const reference = setup();
    const referenceView = render(
      <OverviewMapController {...reference.props} />
    );
    for (let i = 0; i < 240; i++) scene.frame?.({}, 1 / 60);
    const position = reference.camera.position.clone();
    const rotation = reference.camera.quaternion.clone();
    referenceView.unmount();
    const actual = setup();
    render(<OverviewMapController {...actual.props} />);
    for (let i = 0; i < fps * 4; i++) scene.frame?.({}, 1 / fps);
    expect(actual.camera.position.distanceTo(position)).toBeLessThan(0.00001);
    expect(actual.camera.quaternion.angleTo(rotation)).toBeLessThan(0.00001);
  }
);

it('pauses while hidden and discards the first resumed delta without replaying hidden time', () => {
  const { camera, props } = setup();
  render(<OverviewMapController {...props} />);
  scene.frame?.({}, 0.1);
  const position = camera.position.clone();
  const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  document.dispatchEvent(new Event('visibilitychange'));
  scene.frame?.({}, 60);
  expect(camera.position.distanceTo(position)).toBe(0);
  hidden.mockReturnValue(false);
  document.dispatchEvent(new Event('visibilitychange'));
  scene.frame?.({}, 60);
  expect(camera.position.distanceTo(position)).toBe(0);
  scene.frame?.({}, 0.1);
  expect(camera.position.distanceTo(position)).toBeGreaterThan(0);
  hidden.mockRestore();
});
