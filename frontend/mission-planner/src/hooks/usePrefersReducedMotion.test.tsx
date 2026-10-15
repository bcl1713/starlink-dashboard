/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { usePrefersReducedMotion } from './usePrefersReducedMotion';
afterEach(() => vi.unstubAllGlobals());
it('reads initial preference, updates on change, and releases its subscription', () => {
  let matches = true;
  const listeners = new Set<() => void>();
  const media = {
    get matches() {
      return matches;
    },
    addEventListener: (_: string, listener: () => void) =>
      listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) =>
      listeners.delete(listener),
  };
  vi.stubGlobal('matchMedia', () => media);
  const { result, unmount } = renderHook(usePrefersReducedMotion);
  expect(result.current).toBe(true);
  act(() => {
    matches = false;
    listeners.forEach((listener) => listener());
  });
  expect(result.current).toBe(false);
  expect(listeners.size).toBe(1);
  unmount();
  expect(listeners.size).toBe(0);
});
it('supports environments without matchMedia', () => {
  vi.stubGlobal('matchMedia', undefined);
  const { result, unmount } = renderHook(usePrefersReducedMotion);
  expect(result.current).toBe(false);
  unmount();
});
