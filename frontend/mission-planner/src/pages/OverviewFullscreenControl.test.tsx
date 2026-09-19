/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OverviewFullscreenControl } from './OverviewFullscreenControl';
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  Reflect.deleteProperty(document, 'fullscreenElement');
  Reflect.deleteProperty(document.documentElement, 'requestFullscreen');
});
describe('OverviewFullscreenControl', () => {
  it('requests native fullscreen for the application document', async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document.documentElement, 'requestFullscreen', {
      configurable: true,
      value: requestFullscreen,
    });
    render(<OverviewFullscreenControl />);
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Enter fullscreen overview',
      })
    );
    expect(requestFullscreen).toHaveBeenCalledTimes(1);
  });
  it('hides while native fullscreen is active', () => {
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => document.documentElement,
    });
    render(<OverviewFullscreenControl />);
    expect(
      screen.queryByRole('button', {
        name: 'Enter fullscreen overview',
      })
    ).toBeNull();
  });
});
