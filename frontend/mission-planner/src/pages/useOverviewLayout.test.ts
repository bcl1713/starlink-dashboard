/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useOverviewLayout } from './useOverviewLayout';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

function setup(width = 1366, height = 703) {
  document.body.innerHTML =
    '<div><main><div class="overview-map-stage"><div class="overview-globe-viewport"><div class="overview-globe"></div></div><div class="overview-right-overlays"><aside class="globe-legend"><button aria-expanded="false">Legend</button></aside></div></div></main></div>';
  const host = document.body.firstElementChild as HTMLElement;
  const page = host.firstElementChild as HTMLElement;
  const stage = page.firstElementChild as HTMLDivElement;
  const globe = page.querySelector<HTMLElement>('.overview-globe')!;
  Object.defineProperties(host, {
    clientWidth: { value: width },
    clientHeight: { value: height },
  });
  Object.defineProperties(stage, {
    clientWidth: { value: width },
    clientHeight: { value: height },
  });
  vi.spyOn(stage, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(0, 65, width, height)
  );
  vi.spyOn(globe, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(12, 150, 820, 440)
  );
  let resize = () => {};
  const observed = new Set<Element>();
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
  const measure = () =>
    act(() => {
      resize();
      const callback = frame;
      frame = undefined;
      callback?.(0);
    });
  return { page, stage, globe, observed, measure };
}

it('frames the actual renderer rather than its larger panel container', () => {
  const { page, stage, globe, observed } = setup();
  const { result, unmount } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  expect(result.current.mode).toBe('landscape');
  expect(result.current.safeRect).toEqual({
    x: 12,
    y: 12,
    width: 796,
    height: 416,
  });
  expect(observed.has(globe)).toBe(true);
  unmount();
  expect(observed.size).toBe(0);
});

it('keeps the same map composition and framing while the legend opens and closes', () => {
  const { page, stage, measure } = setup();
  const { result } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  const before = result.current.safeRect;
  for (const expanded of ['true', 'false', 'true', 'false']) {
    page.querySelector('button')!.setAttribute('aria-expanded', expanded);
    measure();
    expect(result.current.mode).toBe('landscape');
    expect(result.current.flow).toBe(false);
    expect(result.current.safeRect).toEqual(before);
  }
});

it('updates automatic framing after the renderer resizes without a window resize', () => {
  const { page, stage, globe, measure } = setup();
  const { result } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  vi.mocked(globe.getBoundingClientRect).mockReturnValue(
    new DOMRect(12, 150, 1000, 600)
  );
  measure();
  expect(result.current.safeRect).toEqual({
    x: 12,
    y: 12,
    width: 976,
    height: 576,
  });
});

it('reserves only visible desktop panels and releases their camera space when hidden', () => {
  const { page, stage, globe, measure } = setup(1920, 1080);
  vi.mocked(globe.getBoundingClientRect).mockReturnValue(
    new DOMRect(0, 0, 1920, 1080)
  );
  page.insertAdjacentHTML(
    'beforeend',
    '<div class="overview-metrics-overlays"></div><div class="overview-top-overlays"></div><div class="overview-arrival-overlays"></div>'
  );
  const metrics = page.querySelector('.overview-metrics-overlays')!;
  vi.spyOn(metrics, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(20, 136, 440, 924)
  );
  vi.spyOn(
    page.querySelector('.overview-top-overlays')!,
    'getBoundingClientRect'
  ).mockReturnValue(new DOMRect(20, 20, 1880, 96));
  vi.spyOn(
    page.querySelector('.overview-right-overlays')!,
    'getBoundingClientRect'
  ).mockReturnValue(new DOMRect(1580, 136, 320, 924));
  vi.spyOn(
    page.querySelector('.overview-arrival-overlays')!,
    'getBoundingClientRect'
  ).mockReturnValue(new DOMRect(480, 940, 1080, 120));
  const { result } = renderHook(() =>
    useOverviewLayout({ current: page }, { current: stage }, 'loaded', true)
  );
  expect(result.current.safeRect).toEqual({
    x: 480,
    y: 136,
    width: 1080,
    height: 784,
  });
  metrics.remove();
  measure();
  expect(result.current.safeRect.x).toBe(20);
  expect(result.current.safeRect.width).toBe(1540);
});
