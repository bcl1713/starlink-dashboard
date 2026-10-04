/** @vitest-environment jsdom */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OverviewFullscreenControl } from './OverviewFullscreenControl';
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  Reflect.deleteProperty(document, 'fullscreenElement');
  Reflect.deleteProperty(document.documentElement, 'requestFullscreen');
});
describe('OverviewFullscreenControl', () => {
  it('offers actionable feedback when a trusted local native request rejects', async () => {
    Object.defineProperty(document.documentElement, 'requestFullscreen', {
      configurable: true,
      value: () => Promise.reject(new TypeError('Denied')),
    });
    render(<OverviewFullscreenControl />);
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Enter fullscreen overview' })
      );
    });
    expect(screen.getByRole('status').textContent).toContain(
      'Click Fullscreen in the Overview window to finish.'
    );
  });
  it('reports a missing native API accessibly', async () => {
    render(<OverviewFullscreenControl />);
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Enter fullscreen overview' })
      );
    });
    expect(screen.getByRole('status').textContent).toContain(
      'Fullscreen is unavailable'
    );
  });
  it('shows remote fallback then hides it for actual fullscreen and restores the control on Escape', () => {
    render(<OverviewFullscreenControl feedback="interaction-required" />);
    expect(screen.getByRole('status').textContent).toContain(
      'Click Fullscreen in the Overview window to finish.'
    );
    act(() => {
      Object.defineProperty(document, 'fullscreenElement', {
        configurable: true,
        value: document.documentElement,
        writable: true,
      });
      document.dispatchEvent(new Event('fullscreenchange'));
    });
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    act(() => {
      Object.defineProperty(document, 'fullscreenElement', {
        configurable: true,
        value: null,
      });
      document.dispatchEvent(new Event('fullscreenchange'));
    });
    expect(
      screen.getByRole('button', { name: 'Enter fullscreen overview' })
    ).not.toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });
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
