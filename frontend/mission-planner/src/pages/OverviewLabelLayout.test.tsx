/** @vitest-environment jsdom */
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OverviewLabelLayout } from './OverviewLabelLayout';
import { OverviewMapLabelContent } from './OverviewMapLabel';
import type {
  LabelLayoutRequest,
  LabelLayoutResponse,
} from './overview-label-layout.worker';

const scene = vi.hoisted(() => ({
  gl: { domElement: null as unknown as HTMLCanvasElement },
  frame: null as unknown as (state: { clock: { elapsedTime: number } }) => void,
}));
vi.mock('@react-three/fiber', () => ({
  useThree: (select: (state: typeof scene) => unknown) => select(scene),
  useFrame: (frame: typeof scene.frame) => {
    scene.frame = frame;
  },
}));
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
