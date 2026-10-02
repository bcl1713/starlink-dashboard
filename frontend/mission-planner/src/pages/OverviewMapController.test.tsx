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
vi.mock('@react-three/drei', async () => {
  const [{ default: Impl }, THREE, React] = await Promise.all([
    import('camera-controls'),
    import('three'),
    import('react'),
  ]);
  Impl.install({ THREE });
  return {
    CameraControlsImpl: Impl,
    CameraControls: React.forwardRef((props: Record<string, unknown>, ref) => {
      const control = React.useMemo(() => {
        const Constructor = props.impl as typeof Impl;
        return new Constructor(scene.state.camera as PerspectiveCamera);
      }, [props.impl]);
      React.useImperativeHandle(ref, () => control);
      Object.assign(control, {
        smoothTime: props.smoothTime,
        draggingSmoothTime: props.draggingSmoothTime,
        maxSpeed: props.maxSpeed,
        minDistance: props.minDistance,
        maxDistance: props.maxDistance,
        enabled: props.enabled,
      });
      React.useEffect(() => {
        scene.frame = (_, delta) => {
          control.update(delta);
        };
        const canvas = (scene.state.gl as { domElement: HTMLCanvasElement })
          .domElement;
        control.connect(canvas);
        const events = {
          sleep: props.onSleep as () => void,
          controlstart: props.onControlStart as () => void,
          control: props.onControl as () => void,
        };
        const names = ['sleep', 'controlstart', 'control'] as const;
        for (const name of names) control.addEventListener(name, events[name]);
        return () => {
          for (const name of names)
            control.removeEventListener(name, events[name]);
          control.disconnect();
        };
      }, [control, props.onSleep, props.onControlStart, props.onControl]);
      return null;
    }),
  };
});
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
it.each([5, 30, 60, 144])(
  'moves continuously within the dolly speed cap and settles at %i fps',
  (fps) => {
    const { camera, props } = setup();
    render(<OverviewMapController {...props} />);
    let distance = camera.position.length();
    for (let i = 0; i < fps * 60; i++) {
      scene.frame?.({}, 1 / fps);
      const nextDistance = camera.position.length();
      expect(Math.abs(nextDistance - distance) * fps).toBeLessThanOrEqual(
        1.5001
      );
      distance = nextDistance;
    }
    expect(props.onCameraSettled).toHaveBeenCalledTimes(1);
    const settled = camera.position.clone();
    for (let i = 0; i < fps; i++) scene.frame?.({}, 1 / fps);
    expect(camera.position.distanceTo(settled)).toBeLessThan(0.00001);
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

it('settles first-load route framing without further drift', () => {
  const { camera, props } = setup();
  render(
    <OverviewMapController
      {...props}
      route={[globePosition(35, -100, 2), globePosition(45, -80, 2)]}
    />
  );
  for (let i = 0; i < 3600; i++) scene.frame?.({}, 1 / 60);
  expect(props.onCameraSettled).toHaveBeenCalled();
  const settled = camera.position.clone();
  for (let i = 0; i < 60; i++) scene.frame?.({}, 1 / 60);
  expect(camera.position.distanceTo(settled)).toBeLessThan(0.001);
});

it('preserves follow motion through repeated equivalent position polls', () => {
  const reference = setup();
  const referenceView = render(
    <OverviewMapController {...reference.props} intent="follow" />
  );
  for (let i = 0; i < 240; i++) scene.frame?.({}, 1 / 60);
  const position = reference.camera.position.clone();
  const offset = reference.camera.view!.offsetX;
  referenceView.unmount();
  const actual = setup();
  const view = render(
    <OverviewMapController {...actual.props} intent="follow" />
  );
  for (let i = 0; i < 240; i++) {
    if (i % 60 === 0)
      view.rerender(
        <OverviewMapController
          {...actual.props}
          intent="follow"
          route={[]}
          safeRect={{ ...actual.props.safeRect }}
          aircraft={{ ...actual.props.aircraft! }}
        />
      );
    scene.frame?.({}, 1 / 60);
  }
  expect(actual.camera.position.distanceTo(position)).toBeLessThan(0.00001);
  expect(actual.camera.view!.offsetX).toBeCloseTo(offset, 6);
});

it('resumes an interrupted follow transition when freshness recovers at the same coordinate', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} intent="follow" />);
  scene.frame?.({}, 0.5);
  view.rerender(
    <OverviewMapController {...props} intent="follow" followAvailable={false} />
  );
  const paused = camera.position.clone();
  for (let i = 0; i < 60; i++) scene.frame?.({}, 1 / 60);
  expect(camera.position.distanceTo(paused)).toBeLessThan(0.00001);
  view.rerender(<OverviewMapController {...props} intent="follow" />);
  for (let i = 0; i < 60; i++) scene.frame?.({}, 1 / 60);
  expect(camera.position.distanceTo(paused)).toBeGreaterThan(0.1);
});

it('wheel exploration cancels automatic dolly before applying the wheel movement', () => {
  const { camera, props } = setup();
  render(
    <OverviewMapController
      {...props}
      mode="desktop"
      route={[globePosition(35, -100, 2), globePosition(45, -80, 2)]}
    />
  );
  for (let i = 0; i < 30; i++) scene.frame?.({}, 1 / 60);
  const before = camera.position.length();
  const canvas = (scene.state.gl as { domElement: HTMLCanvasElement })
    .domElement;
  canvas.dispatchEvent(
    new WheelEvent('wheel', { deltaY: 140, bubbles: true, cancelable: true })
  );
  for (let i = 0; i < 60; i++) scene.frame?.({}, 1 / 60);
  expect(camera.position.length()).toBeGreaterThan(before + 0.1);
});

it('reduced-motion wheel zoom changes distance on the next frame', () => {
  const { camera, props } = setup();
  render(<OverviewMapController {...props} mode="desktop" reducedMotion />);
  const before = camera.position.length();
  const canvas = (scene.state.gl as { domElement: HTMLCanvasElement })
    .domElement;
  canvas.dispatchEvent(
    new WheelEvent('wheel', { deltaY: 140, bubbles: true, cancelable: true })
  );
  scene.frame?.({}, 1 / 60);
  expect(camera.position.length()).toBeGreaterThan(before + 0.5);
  const stopped = camera.position.clone();
  for (let i = 0; i < 60; i++) scene.frame?.({}, 1 / 60);
  expect(camera.position.distanceTo(stopped)).toBeLessThan(0.001);
});

it.each(['automatic', 'follow'] as const)(
  'limits rotation and dolly during initial %s framing and Reset',
  (intent) => {
    const { camera, props } = setup();
    const view = render(<OverviewMapController {...props} intent={intent} />);
    for (const resetRevision of [0, 1]) {
      if (resetRevision)
        view.rerender(
          <OverviewMapController
            {...props}
            intent={intent}
            aircraft={{ latitude: -25, longitude: 80 }}
            resetRevision={resetRevision}
          />
        );
      const rotation = camera.quaternion.clone();
      let distance = camera.position.length();
      for (let i = 0; i < 3600; i++) {
        scene.frame?.({}, 1 / 60);
        expect(rotation.angleTo(camera.quaternion) * 60).toBeLessThanOrEqual(
          (10 * Math.PI) / 180 + 0.0001
        );
        expect(
          Math.abs(camera.position.length() - distance) * 60
        ).toBeLessThanOrEqual(1.5001);
        rotation.copy(camera.quaternion);
        distance = camera.position.length();
      }
    }
    if (intent === 'follow')
      expect(camera.position.length()).toBeCloseTo(4.5, 3);
  }
);

it('eases projection changes instead of jumping when the layout changes', () => {
  const { camera, props } = setup();
  const view = render(<OverviewMapController {...props} reducedMotion />);
  const before = camera.view!.offsetX;
  view.rerender(
    <OverviewMapController
      {...props}
      safeRect={{ x: 12, y: 12, width: 280, height: 245 }}
    />
  );
  expect(camera.view!.offsetX).toBe(before);
  scene.frame?.({}, 0.1);
  expect(camera.view!.offsetX).toBeLessThan(before);
  expect(camera.view!.offsetX).toBeGreaterThan(39);
});
