// @vitest-environment jsdom

import { render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const invalidateSize = vi.fn();
const container = document.createElement('div');
const getContainer = vi.fn(() => container);
const observe = vi.fn();
const disconnect = vi.fn();
let frameCallback: FrameRequestCallback | undefined;
const requestFrame = vi.fn((callback: FrameRequestCallback) => {
  frameCallback = callback;
  return 42;
});
const cancelFrame = vi.fn();

vi.mock('leaflet', () => ({
  divIcon: (options: object) => options,
}));

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Marker: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  Polyline: () => null,
  ScaleControl: () => null,
  TileLayer: () => null,
  Tooltip: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
  useMap: () => ({ getContainer, invalidateSize }),
  ZoomControl: () => null,
}));

import { CurrentPositionMap } from './CurrentPositionMap';

beforeEach(() => {
  frameCallback = undefined;
  vi.stubGlobal('requestAnimationFrame', requestFrame);
  vi.stubGlobal('cancelAnimationFrame', cancelFrame);
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe = observe;
      disconnect = disconnect;
    }
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe('CurrentPositionMap size lifecycle', () => {
  it('invalidates the mounted Leaflet map in its scheduled initial layout pass', () => {
    const { unmount } = render(
      <CurrentPositionMap latitude={10} longitude={20} />
    );

    expect(requestFrame).toHaveBeenCalledOnce();
    expect(observe).toHaveBeenCalledWith(container);
    expect(frameCallback).toBeTypeOf('function');

    frameCallback?.(0);

    expect(invalidateSize).toHaveBeenCalledWith({ pan: false });
    unmount();
  });

  it('releases the pending layout frame and observer on unmount', () => {
    const { unmount } = render(
      <CurrentPositionMap latitude={10} longitude={20} />
    );

    expect(frameCallback).toBeTypeOf('function');
    expect(invalidateSize).not.toHaveBeenCalled();

    unmount();

    expect(cancelFrame).toHaveBeenCalledWith(42);
    expect(disconnect).toHaveBeenCalledOnce();
  });
});
