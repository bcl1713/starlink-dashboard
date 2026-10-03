/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useOverviewLayout } from './useOverviewLayout';

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.replaceChildren();
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
