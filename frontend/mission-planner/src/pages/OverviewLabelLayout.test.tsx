/** @vitest-environment jsdom */
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewLabelLayout } from './OverviewLabelLayout';
import { OverviewMapLabelContent } from './OverviewMapLabel';
import type {
  LabelLayoutRequest,
  LabelLayoutResponse,
} from './overview-label-layout.worker';
import * as THREE from 'three';

const scene = vi.hoisted(() => ({
  gl: { domElement: null as unknown as HTMLCanvasElement },
  frame: null as unknown as (state: { clock: { elapsedTime: number } }) => void,
  clock: { elapsedTime: 0 },
  scene: null as unknown as THREE.Scene,
  camera: null as unknown as THREE.Camera,
  get: null as unknown as () => unknown,
}));
vi.mock('@react-three/fiber', () => ({
  useThree: (select: (state: typeof scene) => unknown) => select(scene),
  useFrame: (frame: typeof scene.frame) => {
    scene.frame = frame;
  },
  addAfterEffect: (frame: () => void) => {
    scene.frame = (state) => {
      scene.clock = state.clock;
      frame();
    };
    return () => {};
  },
}));
scene.get = () => scene;
scene.scene = new THREE.Scene();
scene.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
class ControlledWorker {
  static instance: ControlledWorker;
  requests: LabelLayoutRequest[] = [];
  onmessage: ((event: MessageEvent<LabelLayoutResponse>) => void) | null = null;
  constructor() {
    ControlledWorker.instance = this;
  }
  postMessage(request: LabelLayoutRequest) {
    this.requests.push(structuredClone(request));
  }
  terminate() {}
  respond(anchorId: string) {
    const request = this.requests.at(-1)!;
    this.onmessage?.(
      new MessageEvent<LabelLayoutResponse>('message', {
        data: {
          revision: request.revision,
          layout: {
            offsets: { [anchorId]: [12, -14] },
            placements: {},
            groups: [{ anchorId, ids: ['a', 'b'] }],
          },
        },
      })
    );
  }
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('protects the aircraft on a frame between solver ticks and rejects delayed worker visibility', () => {
  vi.stubGlobal('Worker', ControlledWorker);
  vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(100);
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(28);
  let sourceX = 200;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    function (this: HTMLElement) {
      if (this.tagName === 'CANVAS') return new DOMRect(0, 0, 700, 500);
      return new DOMRect(
        this.dataset.labelSource ? sourceX : 180,
        240,
        this.dataset.overviewLabelId ? 0 : 100,
        this.dataset.overviewLabelId ? 0 : 28
      );
    }
  );
  scene.camera.position.set(0, 0, 10);
  scene.camera.lookAt(0, 0, 0);
  scene.camera.updateMatrixWorld();
  const own = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.MeshBasicMaterial()
  );
  own.name = 'overview-own-aircraft';
  own.scale.setScalar(0.1);
  scene.scene.add(own);
  scene.scene.updateMatrixWorld(true);
  const stage = document.createElement('div');
  stage.className = 'overview-map-stage';
  document.body.append(stage);
  scene.gl.domElement = document.createElement('canvas');
  const view = render(
    <>
      <OverviewLabelLayout />
      <OverviewMapLabelContent
        id="traffic"
        kind="adsb"
        text="MYSTC13 · Stale"
      />
    </>,
    { container: stage }
  );
  stage.append(scene.gl.domElement);
  act(() => scene.frame({ clock: { elapsedTime: 1 } }));
  const worker = ControlledWorker.instance;
  const deliver = () =>
    worker.onmessage?.(
      new MessageEvent('message', {
        data: {
          revision: worker.requests.at(-1)!.revision,
          layout: { offsets: { traffic: [20, 0] }, placements: {}, groups: [] },
        },
      })
    );
  act(deliver);
  const source = stage.querySelector<HTMLElement>('[data-label-source]')!;
  expect(source.style.visibility).toBe('visible');
  sourceX = 330;
  act(() => scene.frame({ clock: { elapsedTime: 1.01 } }));
  expect(source.style.visibility).toBe('hidden');
  // A changed text/anchor schedules another solver result while still unsafe.
  act(() => scene.frame({ clock: { elapsedTime: 1.2 } }));
  act(deliver);
  expect(source.style.visibility).toBe('hidden');
  sourceX = 200;
  act(() => scene.frame({ clock: { elapsedTime: 1.21 } }));
  expect(source.style.visibility).toBe('visible');
  view.unmount();
  stage.remove();
  scene.scene.remove(own);
  own.geometry.dispose();
  (own.material as THREE.Material).dispose();
});

it('keeps a newly opened disclosure focused when an older worker result reanchors its group', () => {
  vi.stubGlobal('Worker', ControlledWorker);
  vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(100);
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(28);
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
    function (this: HTMLElement) {
      if (this.tagName === 'CANVAS') return new DOMRect(0, 0, 700, 500);
      return new DOMRect(
        300,
        200,
        this.dataset.overviewLabelId ? 0 : 100,
        this.dataset.overviewLabelId ? 0 : 28
      );
    }
  );
  const stage = document.createElement('div');
  stage.className = 'overview-map-stage';
  scene.gl.domElement = document.createElement('canvas');
  stage.append(scene.gl.domElement);
  document.body.append(stage);
  const view = render(
    <>
      <OverviewLabelLayout />
      <OverviewMapLabelContent id="a" kind="poi" text="Enter" />
      <OverviewMapLabelContent id="b" kind="poi" text="Exit" />
    </>,
    { container: stage }
  );
  // React rendering replaces the canvas; preserve the measured scene boundary.
  stage.append(scene.gl.domElement);
  act(() => scene.frame({ clock: { elapsedTime: 1 } }));
  act(() => ControlledWorker.instance.respond('a'));
  const root = stage.querySelector<HTMLElement>(
    '[data-overview-label-id="a"]'
  )!;
  root.dataset.labelText = 'Enter updated';
  act(() => scene.frame({ clock: { elapsedTime: 2 } }));
  const details = root.querySelector('details')!;
  const summary = details.querySelector('summary')!;
  summary.focus();
  details.open = true;
  act(() => scene.frame({ clock: { elapsedTime: 3 } }));
  act(() => ControlledWorker.instance.respond('b'));
  expect(details.open).toBe(true);
  expect(document.activeElement).toBe(summary);
  const queued = ControlledWorker.instance.requests.at(-1)!;
  expect(queued.labels).toEqual([]);
  expect(queued.reserved).toContainEqual({
    x: 296,
    y: 196,
    width: 8,
    height: 8,
  });
  view.unmount();
  stage.remove();
});
