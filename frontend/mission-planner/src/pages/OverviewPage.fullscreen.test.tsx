// @vitest-environment jsdom

import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OverviewPage } from './OverviewPage';
import { createOverviewHistoryStore } from './OverviewPage/overviewHistoryStore';
import { useOverviewData } from './OverviewPage/useOverviewData';

vi.mock('./OverviewPage/useOverviewData', () => ({
  useOverviewData: vi.fn(),
}));

const sourceState = {
  loading: false,
  stale: false,
  error: null,
  lastSuccess: new Date('2026-09-02T12:00:00Z'),
  recovering: false,
  recoveredAt: null,
};

function data() {
  return {
    cadence: 5 as const,
    setCadence: vi.fn(),
    status: null,
    statusMessage: 'No successful update',
    history: createOverviewHistoryStore(),
    gep: null,
    gepState: sourceState,
    pois: [],
    poiState: sourceState,

    mapOverlays: {
      route: { west: [], east: [] },
      activeLinks: {
        normal: { west: [], east: [] },
        warning: { west: [], east: [] },
      },
    },
    mapState: sourceState,
    now: new Date('2026-09-02T12:00:00Z'),
    summaries: {
      latency: { current: null, min: null, average: null, max: null },
      packetLoss: { current: null, min: null, average: null, max: null },
    },
    refreshStatus: vi.fn().mockResolvedValue(undefined),
    reconcileHistory: vi.fn().mockResolvedValue(undefined),
    refreshGep: vi.fn().mockResolvedValue(undefined),
    refreshPois: vi.fn().mockResolvedValue(undefined),
    refreshMap: vi.fn().mockResolvedValue(undefined),
  };
}

beforeEach(() => {
  vi.mocked(useOverviewData).mockReturnValue(data());
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value: null,
    writable: true,
  });
});

describe('OverviewPage fullscreen control', () => {
  it('contains document scroll while the mounted overview root is fullscreen', async () => {
    render(<OverviewPage />);
    const root = screen.getByTestId('overview-root');
    root.requestFullscreen = vi.fn().mockResolvedValue(undefined);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Enter fullscreen' }));
    });
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: root,
    });
    act(() => document.dispatchEvent(new Event('fullscreenchange')));

    expect(
      document.documentElement.classList.contains('overview-fullscreen-active')
    ).toBe(true);
    expect(root.classList.contains('overview-page--fullscreen')).toBe(true);

    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: null,
    });
    act(() => document.dispatchEvent(new Event('fullscreenchange')));
    expect(
      document.documentElement.classList.contains('overview-fullscreen-active')
    ).toBe(false);
  });

  it('targets the mounted overview root and keeps its selected cadence mounted', async () => {
    render(<OverviewPage />);
    const root = screen.getByTestId('overview-root');
    root.requestFullscreen = vi.fn().mockResolvedValue(undefined);
    const rootBeforeEntry = root;

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Enter fullscreen' }));
    });
    expect(root.requestFullscreen).toHaveBeenCalledOnce();

    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: root,
    });
    act(() => document.dispatchEvent(new Event('fullscreenchange')));

    expect(
      screen.getByRole('button', { name: 'Exit fullscreen' })
    ).toBeTruthy();
    expect(
      (screen.getByLabelText('Refresh cadence') as HTMLSelectElement).value
    ).toBe('5');
    expect(screen.getByTestId('overview-root')).toBe(rootBeforeEntry);
  });

  it('shows a visible fallback after native fullscreen rejects', async () => {
    render(<OverviewPage />);
    const root = screen.getByTestId('overview-root');
    root.requestFullscreen = vi.fn().mockRejectedValue(new Error('denied'));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Enter fullscreen' }));
    });

    expect(screen.getByRole('status').textContent).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );
  });
});
