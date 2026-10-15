/** @vitest-environment jsdom */

import { act, create } from '@react-three/test-renderer';
import { reconciler, type RootStore } from '@react-three/fiber';
import { isValidElement, StrictMode, type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import type {
  AnimatedFlowResources,
  FlowEmitterConfig,
  FlowLineResources,
  FlowPoint,
} from './overview-animated-flow-line-rendering';

const observed = vi.hoisted(() => ({
  resources: [] as AnimatedFlowResources[],
  ribbons: [] as THREE.BufferGeometry[],
  lines: [] as FlowLineResources[],
  disposed: new Map<unknown, number>(),
}));

vi.mock('./overview-animated-flow-line-rendering', async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import('./overview-animated-flow-line-rendering')
    >();
  return {
    ...actual,
    createFlowLineResources: (
      ...args: Parameters<typeof actual.createFlowLineResources>
    ) => {
      const resources = actual.createFlowLineResources(...args);
      observed.lines.push(resources);
      for (const resource of [resources.geometry, resources.material]) {
        resource.addEventListener('dispose', () => {
          observed.disposed.set(
            resource,
            (observed.disposed.get(resource) ?? 0) + 1
          );
        });
      }
      return resources;
    },
    createAnimatedFlowResources: (
      ...args: Parameters<typeof actual.createAnimatedFlowResources>
    ) => {
      const resources = actual.createAnimatedFlowResources(...args);
      observed.resources.push(resources);
      for (const resource of [resources.geometry, resources.material]) {
        resource.addEventListener('dispose', () => {
          observed.disposed.set(
            resource,
            (observed.disposed.get(resource) ?? 0) + 1
          );
        });
      }
      return resources;
    },
  };
});

vi.mock('./globe-route-ribbon-geometry', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('./globe-route-ribbon-geometry')>();
  return {
    ...actual,
    createGlobeRouteRibbonGeometry: (
      ...args: Parameters<typeof actual.createGlobeRouteRibbonGeometry>
    ) => {
      const geometry = actual.createGlobeRouteRibbonGeometry(...args);
      observed.ribbons.push(geometry);
      geometry.addEventListener('dispose', () => {
        observed.disposed.set(
          geometry,
          (observed.disposed.get(geometry) ?? 0) + 1
        );
      });
      return geometry;
    },
  };
});

import {
  AnimatedFlowLine,
  type AnimatedFlowLineProps,
} from './AnimatedFlowLine';
import { routeFlowEmitters } from './overview-flow-consumers';

const points: readonly FlowPoint[] = [
  [0, 0, 0],
  [10, 0, 0],
];
const forward: FlowEmitterConfig = {
  enabled: true,
  rate: 20,
  speed: 1,
  color: '#ffb000',
  size: 6,
  brightness: 1,
  maxParticles: 100,
};
const reverse: FlowEmitterConfig = { ...forward, color: '#54f0ff' };
const mediaListeners = new Set<() => void>();
let reduced = false;
let hidden = false;

type Renderer = Awaited<ReturnType<typeof create>>;
const views = new Set<Renderer>();
const roots = new Set<RootStore>();

async function render(element: ReactNode) {
  // Fiber wraps children in its Provider and creates a non-strict root. React
  // 19 does not replay effects for a nested StrictMode in that root. Preserve
  // the lifecycle probe by setting the reconciler's real root strictness flag.
  const createContainer = reconciler.createContainer;
  const strictRoot =
    isValidElement(element) && element.type === StrictMode
      ? vi
          .spyOn(reconciler, 'createContainer')
          .mockImplementation((...args) => {
            args[3] = true;
            return createContainer(...args);
          })
      : undefined;
  let view: Renderer;
  try {
    view = await create(element, {
      width: 1920,
      height: 1080,
      dpr: 2,
      camera: { fov: 50 },
    });
  } finally {
    strictRoot?.mockRestore();
  }
  views.add(view);
  roots.add(view.scene.fiber.root);
  return {
    scene: view.scene,
    rerender: view.update,
    unmount: async () => {
      await view.unmount();
      views.delete(view);
    },
  };
}

async function frame(delta = 0.1) {
  await act(async () => {
    for (const view of views) await view.advanceFrames(1, delta);
  });
}
async function visibility(value: boolean) {
  await act(async () => {
    hidden = value;
    document.dispatchEvent(new Event('visibilitychange'));
  });
}
async function motion(value: boolean) {
  await act(async () => {
    reduced = value;
    for (const listener of mediaListeners) listener();
  });
}
function liveLines() {
  return observed.lines.filter(
    (resources) => !observed.disposed.has(resources.geometry)
  );
}
function latest() {
  const resources = observed.resources.at(-1);
  expect(resources).toBeDefined();
  return resources!;
}
function expectDisposed(resources: AnimatedFlowResources) {
  expect(resources.geometry.drawRange.count).toBe(0);
  expect(observed.disposed.get(resources.geometry)).toBe(1);
  expect(observed.disposed.get(resources.material)).toBe(1);
}
function line(props: Partial<AnimatedFlowLineProps> = {}) {
  return (
    <AnimatedFlowLine
      points={points}
      forward={forward}
      reverse={reverse}
      {...props}
    />
  );
}

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  reduced = false;
  hidden = false;
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => hidden,
  });
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => (hidden ? 'hidden' : 'visible'),
  });
  vi.stubGlobal('matchMedia', () => ({
    get matches() {
      return reduced;
    },
    addEventListener: (_event: string, listener: () => void) =>
      mediaListeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) =>
      mediaListeners.delete(listener),
  }));
});

afterEach(async () => {
  for (const view of views) await view.unmount();
  views.clear();
  for (const root of roots)
    expect(root.getState().internal.subscribers).toHaveLength(0);
  roots.clear();
  expect(mediaListeners.size).toBe(0);
  for (const resources of observed.resources) expectDisposed(resources);
  observed.resources.length = 0;
  for (const resources of observed.lines) {
    expect(observed.disposed.get(resources.geometry)).toBe(1);
    expect(observed.disposed.get(resources.material)).toBe(1);
  }
  observed.lines.length = 0;
  for (const geometry of observed.ribbons)
    expect(observed.disposed.get(geometry)).toBe(1);
  observed.ribbons.length = 0;
  observed.disposed.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AnimatedFlowLine lifecycle', () => {
  it('emits only reverse particles for existing reverse-only consumers', async () => {
    const view = await render(line({ forward: undefined }));
    const group = view.scene.instance.children[0];
    expect(group).toBeInstanceOf(THREE.Group);
    expect(group.children.map((branch) => branch.children[0].type)).toEqual([
      'Line2',
      'Line2',
      'Line2',
      'Points',
    ]);
    expect(liveLines()).toHaveLength(3);
    await frame();
    const resources = latest();
    expect(resources.geometry.drawRange.count).toBe(2);
    const colors = resources.geometry.getAttribute('color');
    const expected = new THREE.Color('#54f0ff');
    expect(colors.getX(0)).toBeCloseTo(expected.r);
    expect(resources.geometry.getAttribute('position').getX(0)).toBe(10);
  });

  it('drops existing particles when a direction stops before another frame', async () => {
    const view = await render(line());
    await frame();
    const resources = latest();
    expect(resources.geometry.drawRange.count).toBe(4);
    await view.rerender(line({ forward: { ...forward, enabled: false } }));
    expect(resources.geometry.drawRange.count).toBe(2);
    expect(resources.geometry.getAttribute('position').getX(0)).toBe(10);
    await view.rerender(
      line({
        forward: { ...forward, enabled: false },
        reverse: { ...reverse, enabled: false },
      })
    );
    expectDisposed(resources);
    expect(liveLines()).toHaveLength(3);
    await view.rerender(line());
    expect(latest()).not.toBe(resources);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame();
    expect(latest().geometry.drawRange.count).toBe(4);
  });

  it('clears warning particles immediately and resumes without old progress or remainder', async () => {
    const emitter = { ...forward, rate: 15 };
    const view = await render(line({ forward: emitter, reverse: undefined }));
    await frame();
    await frame();
    const previous = latest();
    await view.rerender(
      line({ forward: { ...emitter, enabled: false }, reverse: undefined })
    );
    expectDisposed(previous);
    await view.rerender(line({ forward: emitter, reverse: undefined }));
    await frame(0.05);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame(0.05);
    expect(latest().geometry.drawRange.count).toBe(1);
    expect(latest().geometry.getAttribute('position').getX(0)).toBe(0);
  });

  it.each<{ points: readonly FlowPoint[] }>([
    { points: [] },
    { points: [[0, 0, 0]] },
    {
      points: [
        [0, 0, 0],
        [0, 0, 0],
      ],
    },
    {
      points: [
        [0, 0, 0],
        [NaN, 0, 0],
      ],
    },
  ])(
    'releases particles for invalid path $points',
    async ({ points: invalid }) => {
      const view = await render(line());
      await frame();
      const resources = latest();
      await view.rerender(line({ points: invalid }));
      expectDisposed(resources);
      const versions = Object.values(resources.geometry.attributes).map(
        (a) => (a as THREE.BufferAttribute).version
      );
      await frame();
      expect(
        Object.values(resources.geometry.attributes).map(
          (a) => (a as THREE.BufferAttribute).version
        )
      ).toEqual(versions);
      expect(observed.resources).toHaveLength(1);
    }
  );

  it('clears particles before drawing changed endpoints', async () => {
    const view = await render(line());
    await frame();
    const old = latest();
    const replacement: FlowPoint[] = [
      [20, 0, 0],
      [30, 0, 0],
    ];
    await view.rerender(line({ points: replacement }));
    expect(old.geometry.drawRange.count).toBe(0);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame();
    expect(latest().geometry.getAttribute('position').getX(0)).toBe(20);
  });

  it('preserves in-flight progress as the same link endpoint moves', async () => {
    const view = await render(line({ particleKey: 'pop-a' }));
    await frame();
    await frame();
    await frame();
    const resources = latest();
    expect(resources.geometry.drawRange.count).toBe(12);
    expect(resources.geometry.getAttribute('position').getX(0)).toBeCloseTo(
      0.2
    );

    await view.rerender(
      line({
        points: [
          [1, 0, 0],
          [21, 0, 0],
        ],
        particleKey: 'pop-a',
        forward: { ...forward, rate: 10 },
      })
    );
    expect(latest()).toBe(resources);
    expect(observed.disposed.has(resources.geometry)).toBe(false);
    expect(resources.geometry.drawRange.count).toBe(12);
    expect(resources.geometry.getAttribute('position').getX(0)).toBeCloseTo(
      1.4
    );
    expect(resources.geometry.getAttribute('position').getX(2)).toBeCloseTo(
      20.6
    );
    await frame();
    expect(resources.geometry.drawRange.count).toBe(15);
    expect(resources.geometry.getAttribute('position').getX(0)).toBeCloseTo(
      1.5
    );
    expect(resources.geometry.getAttribute('position').getX(2)).toBeCloseTo(
      20.5
    );
  });

  it('starts fresh when the moving link destination changes', async () => {
    const view = await render(line({ particleKey: 'pop-a' }));
    await frame();
    const old = latest();
    await view.rerender(line({ particleKey: 'pop-b' }));
    expectDisposed(old);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame();
    expect(latest().geometry.getAttribute('position').getX(0)).toBe(0);
  });

  it('disposes hidden particles, writes no paused buffers, and discards resumed delta', async () => {
    await render(line());
    await frame();
    const old = latest();
    await visibility(true);
    expectDisposed(old);
    expect(liveLines()).toHaveLength(3);
    const position = old.geometry.getAttribute(
      'position'
    ) as THREE.BufferAttribute;
    const version = position.version;
    const values = Array.from(position.array);
    await frame(60);
    expect(position.version).toBe(version);
    expect(Array.from(position.array)).toEqual(values);
    expect(observed.resources).toHaveLength(1);
    await visibility(false);
    expect(latest()).not.toBe(old);
    await frame(60);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame();
    expect(latest().geometry.drawRange.count).toBe(4);
  });

  it('keeps line geometry while reduced motion releases particle resources', async () => {
    await render(line());
    await frame();
    const old = latest();
    await motion(true);
    expectDisposed(old);
    expect(liveLines()).toHaveLength(3);
    const version = (
      old.geometry.getAttribute('position') as THREE.BufferAttribute
    ).version;
    await frame(60);
    expect(
      (old.geometry.getAttribute('position') as THREE.BufferAttribute).version
    ).toBe(version);
    await motion(false);
    await frame();
    expect(latest().geometry.drawRange.count).toBe(4);
    expect(latest().geometry.getAttribute('position').getX(0)).toBe(0);
  });

  it.each(['hidden', 'reduced', 'disabled', 'ineligible'])(
    'allocates no particles initially %s',
    async (reason) => {
      hidden = reason === 'hidden';
      reduced = reason === 'reduced';
      await render(
        line({
          forward:
            reason === 'disabled' ? { ...forward, enabled: false } : forward,
          reverse: undefined,
          canAnimate: () => reason !== 'ineligible',
        })
      );
      await frame();
      expect(observed.resources).toHaveLength(0);
    }
  );

  it('rechecks wall-clock eligibility on every frame before the next UI tick', async () => {
    let now = 9000;
    vi.spyOn(Date, 'now').mockImplementation(() => now);
    await render(line({ canAnimate: () => Date.now() < 10000 }));
    await frame();
    const old = latest();
    expect(old.geometry.drawRange.count).toBe(4);
    now = 10000;
    await frame();
    expectDisposed(old);
    expect(liveLines()).toHaveLength(3);
    const version = (
      old.geometry.getAttribute('position') as THREE.BufferAttribute
    ).version;
    await frame();
    expect(
      (old.geometry.getAttribute('position') as THREE.BufferAttribute).version
    ).toBe(version);
    now = 9000;
    await frame(60);
    expect(latest()).not.toBe(old);
    expect(latest().geometry.drawRange.count).toBe(0);
    await frame();
    expect(latest().geometry.drawRange.count).toBe(4);
  });

  it('checks eligibility on hidden return before allocating or waiting for a frame', async () => {
    let eligible = true;
    await render(line({ canAnimate: () => eligible }));
    await frame();
    await visibility(true);
    eligible = false;
    await visibility(false);
    expect(observed.resources).toHaveLength(1);
    await frame(60);
    expect(observed.resources).toHaveLength(1);
  });

  it('clamps active delta and reuses typed buffers and prepared geometry', async () => {
    await render(line({ forward, reverse: undefined }));
    await frame(60);
    const resources = latest();
    expect(resources.geometry.drawRange.count).toBe(2);
    const array = resources.geometry.getAttribute('position').array;
    await frame(60);
    expect(resources.geometry.drawRange.count).toBe(4);
    expect(resources.geometry.getAttribute('position').getX(0)).toBeCloseTo(
      0.1
    );
    expect(resources.geometry.getAttribute('position').array).toBe(array);
    expect(observed.resources).toHaveLength(1);
  });

  it('releases every allocation exactly once across StrictMode and repeated toggles/mounts', async () => {
    const add = vi.spyOn(document, 'addEventListener');
    const remove = vi.spyOn(document, 'removeEventListener');
    for (let mount = 0; mount < 3; mount += 1) {
      const view = await render(<StrictMode>{line()}</StrictMode>);
      await frame();
      expect(latest().geometry.drawRange.count).toBe(4);
      expect(observed.disposed.has(latest().geometry)).toBe(false);
      for (let toggle = 0; toggle < 3; toggle += 1) {
        await visibility(true);
        await visibility(false);
        await frame(60);
        expect(latest().geometry.drawRange.count).toBe(0);
        await frame();
        expect(latest().geometry.drawRange.count).toBe(4);
        expect(observed.disposed.has(latest().geometry)).toBe(false);
      }
      await view.unmount();
    }
    const subscriptions = add.mock.calls.filter(
      ([event]) => event === 'visibilitychange'
    );
    const removals = remove.mock.calls.filter(
      ([event]) => event === 'visibilitychange'
    );
    expect(subscriptions.length).toBeGreaterThan(0);
    expect(removals.map(([, listener]) => listener)).toEqual(
      subscriptions.map(([, listener]) => listener)
    );
  });

  it('preserves normal blending for a custom core that omits the optional override', async () => {
    await render(
      line({ core: { color: '#123456', linewidth: 2, opacity: 0.8 } })
    );
    expect(liveLines()[2].material.blending).toBe(THREE.NormalBlending);
    expect(liveLines()[0].material.blending).toBe(THREE.AdditiveBlending);
  });

  it('owns live short-line resources across StrictMode and releases every setup exactly once', async () => {
    const view = await render(<StrictMode>{line()}</StrictMode>);
    expect(observed.lines).toHaveLength(6);
    for (const resources of observed.lines.slice(3)) {
      expect(observed.disposed.has(resources.geometry)).toBe(false);
      expect(observed.disposed.has(resources.material)).toBe(false);
      expect(resources.line.type).toBe('Line2');
      expect(resources.geometry.getAttribute('instanceEnd').getX(0)).toBe(10);
    }
    await frame();
    const live = liveLines();
    expect(
      live.map(({ material }) => [
        material.linewidth,
        material.opacity,
        material.color.getHexString(),
        material.blending,
      ])
    ).toEqual([
      [8, 0.12, 'ffb000', THREE.AdditiveBlending],
      [4, 0.3, 'ffb000', THREE.AdditiveBlending],
      [1.25, 0.95, 'ffd86b', THREE.NormalBlending],
    ]);
    for (const { material } of live) {
      expect(material.resolution.toArray()).toEqual([1920, 1080]);
      expect(material.depthTest).toBe(true);
      expect(material.depthWrite).toBe(false);
      expect(material.toneMapped).toBe(false);
      expect(material.transparent).toBe(true);
      expect(material.polygonOffsetFactor).toBe(-1);
      expect(material.polygonOffsetUnits).toBe(-2);
    }
    await view.unmount();
    for (const resources of observed.lines) {
      expect(observed.disposed.get(resources.geometry)).toBe(1);
      expect(observed.disposed.get(resources.material)).toBe(1);
    }
  });

  it('retains the real ribbon through pauses and releases it on endpoint replacement/unmount', async () => {
    const route: FlowPoint[] = [
      [2, 0, 0],
      [2, 2, 0],
      [0, 2, 0],
    ];
    const view = await render(line({ points: route }));
    const geometry = observed.ribbons.at(-1)!;
    await frame();
    await visibility(true);
    await motion(true);
    await visibility(false);
    expect(observed.ribbons).toHaveLength(1);
    expect(observed.disposed.has(geometry)).toBe(false);
    await view.rerender(
      line({
        points: [
          [0, 2, 0],
          [0, 2, 2],
          [0, 0, 2],
        ],
      })
    );
    expect(observed.disposed.get(geometry)).toBe(1);
    expect(observed.disposed.has(observed.ribbons.at(-1))).toBe(false);
    await view.unmount();
  });

  it('creates fresh ribbon resources during StrictMode setup and disposes each exactly once', async () => {
    const materials: unknown[] = [];
    const disposed = vi.spyOn(THREE.Material.prototype, 'dispose');
    const view = await render(
      <StrictMode>
        {line({
          points: [
            [2, 0, 0],
            [2, 2, 0],
            [0, 2, 0],
          ],
        })}
      </StrictMode>
    );
    expect(observed.disposed.has(observed.ribbons.at(-1))).toBe(false);
    await frame();
    materials.push(...disposed.mock.instances);
    expect(new Set(materials).size).toBe(4);
    await view.unmount();
    const counts = new Map<unknown, number>();
    for (const material of disposed.mock.instances)
      counts.set(material, (counts.get(material) ?? 0) + 1);
    // Two independent setups, three line materials and one particle material each.
    expect(counts.size).toBe(8);
    expect([...counts.values()]).toEqual(Array(8).fill(1));
  });

  it('retains route traversal with showLine false and default eligibility', async () => {
    const route: FlowPoint[] = [
      [2, 0, 0],
      [2, 2, 0],
      [0, 2, 0],
    ];
    await render(
      line({ points: route, ...routeFlowEmitters(), showLine: false })
    );
    expect(liveLines()).toHaveLength(0);
    for (let index = 0; index < 20; index += 1) await frame();
    const resources = latest();
    expect(resources.geometry.drawRange.count).toBeGreaterThan(0);
    const positions = resources.geometry.getAttribute('position');
    expect(positions.getY(0)).toBeGreaterThan(0);
    expect(positions.getX(0)).toBeLessThanOrEqual(2);
  });
});

it('orbital multi-hop geometry retains normalized progress and clears on inferred handover', async () => {
  const key = 'orbital:["a",["1","2"],[6378,0,0]]';
  const view = await render(
    line({
      points: [
        [0, 0, 0],
        [5, 0, 0],
        [10, 0, 0],
      ],
      particleKey: key,
    })
  );
  await frame();
  await frame();
  await frame();
  const old = latest();
  const count = old.geometry.drawRange.count;
  await view.rerender(
    line({
      points: [
        [1, 0, 0],
        [11, 0, 0],
        [21, 0, 0],
      ],
      particleKey: key,
    })
  );
  expect(latest()).toBe(old);
  expect(old.geometry.drawRange.count).toBe(count);
  expect(old.geometry.getAttribute('position').getX(0)).toBeCloseTo(1.4);
  await view.rerender(
    line({
      points: [
        [1, 0, 0],
        [11, 0, 0],
        [21, 0, 0],
      ],
      particleKey: 'orbital:["b",["1","3"],[6378,0,0]]',
    })
  );
  expectDisposed(old);
  expect(latest().geometry.drawRange.count).toBe(0);
  await frame();
  expect(latest().geometry.drawRange.count).toBe(4);
});
