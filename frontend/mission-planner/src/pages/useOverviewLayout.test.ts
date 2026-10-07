/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useOverviewLayout } from './useOverviewLayout';

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

it('keeps the landscape camera opening left of the map buttons as well as the satellite panel', () => {
  document.body.innerHTML =
    '<div><main data-layout="landscape"><div class="overview-map-stage"><div class="overview-map-controls"></div><div class="overview-arrival"></div></div></main></div>';
  const host = document.body.firstElementChild as HTMLElement;
  const page = host.firstElementChild as HTMLElement;
  const stage = page.firstElementChild as HTMLDivElement;
  Object.defineProperties(host, {
    clientWidth: { value: 1024 },
    clientHeight: { value: 550 },
    offsetWidth: { value: 1024 },
    offsetHeight: { value: 550 },
  });
  Object.defineProperties(stage, {
    clientWidth: { value: 756 },
    clientHeight: { value: 440 },
  });
  vi.spyOn(stage, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, 100, 756, 440)
  );
  vi.spyOn(
    page.querySelector('.overview-map-controls')!,
    'getBoundingClientRect'
  ).mockReturnValue(new DOMRect(432, 112, 160, 80));
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    }
  );
  const { result } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  expect(result.current.mode).toBe('landscape');
  expect(
    result.current.safeRect.x + result.current.safeRect.width
  ).toBeLessThanOrEqual(400);
});

it('retains the flow fallback when its scrollbar changes content width, then resets on frame resize', () => {
  document.body.innerHTML =
    '<div><main data-layout="stacked"><div class="overview-map-stage"><div class="overview-right-overlays"></div><div class="overview-arrival"></div></div></main></div>';
  const host = document.body.firstElementChild as HTMLElement;
  const page = host.firstElementChild as HTMLElement;
  const stage = page.firstElementChild as HTMLDivElement;
  const right = page.querySelector<HTMLElement>('.overview-right-overlays')!;
  const arrival = page.querySelector<HTMLElement>('.overview-arrival')!;
  let frameWidth = 1920;
  let contentWidth = 1920;
  let height = 835;
  let rightHeight = 200;
  Object.defineProperties(host, {
    clientWidth: { get: () => contentWidth },
    clientHeight: { get: () => height },
    offsetWidth: { get: () => frameWidth },
    offsetHeight: { get: () => height },
  });
  Object.defineProperties(stage, {
    clientWidth: { value: 1200 },
    clientHeight: { value: 380 },
  });
  vi.spyOn(right, 'getBoundingClientRect').mockImplementation(
    () => new DOMRect(0, 0, 160, rightHeight)
  );
  vi.spyOn(arrival, 'getBoundingClientRect').mockImplementation(
    () => new DOMRect(0, 0, 1176, 80)
  );
  let resize = () => {};
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback;
      }
      observe() {}
      disconnect() {}
    }
  );
  let frame: FrameRequestCallback | undefined;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frame = callback;
    return 1;
  });
  vi.stubGlobal('cancelAnimationFrame', () => {
    frame = undefined;
  });
  const { result, unmount } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  expect(result.current.mode).toBe('stacked');
  expect(result.current.flow).toBe(true);
  // Moving overlays into flow makes them shorter but adds a vertical scrollbar.
  rightHeight = 100;
  const measure = () =>
    act(() => {
      resize();
      const callback = frame;
      frame = undefined;
      callback?.(0);
    });
  for (const width of [1905, 1920, 1905]) {
    contentWidth = width;
    measure();
    expect(result.current.flow).toBe(true);
  }
  // An actual window resize must still release the fallback.
  frameWidth = contentWidth = 1500;
  measure();
  expect(result.current.mode).toBe('stacked');
  expect(result.current.flow).toBe(false);
  height = 1080;
  measure();
  expect(result.current.mode).toBe('desktop');
  expect(result.current.flow).toBe(false);
  unmount();
});

it('remeasures growing display feedback and moves oversized controls into flow without a frame resize', () => {
  document.body.innerHTML =
    '<div><main data-layout="landscape"><div class="overview-map-stage"><div class="overview-right-overlays"><div class="overview-display-controls"></div></div><div class="overview-arrival"></div></div></main></div>';
  const host = document.body.firstElementChild as HTMLElement;
  const page = host.firstElementChild as HTMLElement;
  const stage = page.firstElementChild as HTMLDivElement;
  const right = page.querySelector<HTMLElement>('.overview-right-overlays')!;
  const display = page.querySelector<HTMLElement>(
    '.overview-display-controls'
  )!;
  const arrival = page.querySelector<HTMLElement>('.overview-arrival')!;
  Object.defineProperties(host, {
    clientWidth: { value: 844 },
    clientHeight: { value: 325 },
    offsetWidth: { value: 844 },
    offsetHeight: { value: 325 },
  });
  Object.defineProperties(stage, {
    clientWidth: { value: 568 },
    clientHeight: { value: 220 },
  });
  let rightHeight = 100;
  vi.spyOn(right, 'getBoundingClientRect').mockImplementation(
    () => new DOMRect(0, 0, 544, rightHeight)
  );
  vi.spyOn(arrival, 'getBoundingClientRect').mockImplementation(
    () => new DOMRect(0, 0, 544, 70)
  );
  const observed = new Set<Element>();
  let resize = () => {};
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback;
      }
      observe(node: Element) {
        observed.add(node);
      }
      disconnect() {
        observed.clear();
      }
    }
  );
  let frame: FrameRequestCallback | undefined;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frame = callback;
    return 1;
  });
  vi.stubGlobal('cancelAnimationFrame', () => {
    frame = undefined;
  });
  const pageRef = { current: page },
    stageRef = { current: stage };
  const { result, unmount } = renderHook(() =>
    useOverviewLayout(pageRef, stageRef, 'loaded', true)
  );
  expect(result.current.mode).toBe('landscape');
  expect(result.current.flow).toBe(false);
  // Local feedback can grow without changing Overview's content key. Deliver
  // the size notification only if the real hook subscribed to this container.
  rightHeight = 200;
  act(() => {
    if (observed.has(display)) resize();
    const callback = frame;
    frame = undefined;
    callback?.(0);
  });
  expect(result.current.mode).toBe('stacked');
  expect(result.current.flow).toBe(true);
  unmount();
  expect(observed.size).toBe(0);
});

it('releases an overflow fallback when panels are hidden at the same viewport size', () => {
  document.body.innerHTML =
    '<div><main data-layout="landscape"><div class="overview-map-stage"><div class="overview-right-overlays"></div><div class="overview-arrival"></div></div></main></div>';
  const host = document.body.firstElementChild as HTMLElement;
  const page = host.firstElementChild as HTMLElement;
  const stage = page.firstElementChild as HTMLDivElement;
  Object.defineProperties(host, {
    clientWidth: { value: 1024 },
    clientHeight: { value: 550 },
    offsetWidth: { value: 1024 },
    offsetHeight: { value: 550 },
  });
  Object.defineProperties(stage, {
    clientWidth: { value: 756 },
    clientHeight: { value: 440 },
  });
  let rightHeight = 500;
  vi.spyOn(
    page.querySelector('.overview-right-overlays')!,
    'getBoundingClientRect'
  ).mockImplementation(() => new DOMRect(0, 0, 160, rightHeight));
  vi.spyOn(
    page.querySelector('.overview-arrival')!,
    'getBoundingClientRect'
  ).mockReturnValue(new DOMRect(0, 0, 600, 80));
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    }
  );
  const { result, rerender, unmount } = renderHook(
    ({ visibility }) =>
      useOverviewLayout(
        { current: page },
        { current: stage },
        'loaded',
        true,
        visibility
      ),
    { initialProps: { visibility: 'panels-visible' } }
  );
  expect(result.current.mode).toBe('stacked');
  expect(result.current.flow).toBe(true);
  page.dataset.layout = 'stacked';
  rightHeight = 80;
  rerender({ visibility: 'panels-hidden' });
  expect(result.current.mode).toBe('landscape');
  expect(result.current.flow).toBe(false);
  unmount();
});
