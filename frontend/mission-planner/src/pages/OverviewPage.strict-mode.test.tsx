import { fireEvent, render, screen } from '@testing-library/react';
import { StrictMode, forwardRef, useImperativeHandle } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OverviewPage } from './OverviewPage';
import { makeOverviewSnapshot } from './OverviewPage/OperationalMap/test-fixtures';
import { OVERVIEW_PREFERENCES_STORAGE_KEY } from './OverviewPage/preferences';

const mocks = vi.hoisted(() => ({
  manualRefresh: vi.fn(),
  retryRadar: vi.fn(),
  reportRadarResult: vi.fn(),
  focusCoordinates: vi.fn(),
  useOverviewData: vi.fn(),
}));

vi.mock('./OverviewPage/useOverviewClock', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./OverviewPage/useOverviewClock')>()),
  useOverviewClock: () => new Date('2026-08-31T05:00:00.000Z'),
}));

vi.mock('./OverviewPage/useOverviewData', () => ({
  useOverviewData: (options: unknown) => mocks.useOverviewData(options),
}));

vi.mock('./OverviewPage/OperationalMap', () => ({
  OperationalMap: forwardRef((_props: Record<string, unknown>, ref) => {
    useImperativeHandle(ref, () => ({
      fitToAvailableLayers: vi.fn(),
      focusCoordinates: mocks.focusCoordinates,
    }));
    return <div data-testid="operational-map">Map tree</div>;
  }),
}));

function Panel(props: Record<string, unknown>) {
  const Heading = props.headingAs === 'h3' ? 'h3' : 'h2';
  return (
    <article>
      <Heading>Panel</Heading>
      <button type="button" onClick={() => (props.onRetry as () => void)()}>
        Retry panel
      </button>
    </article>
  );
}

vi.mock('./OverviewPage/components/NetworkLatencyPanel', () => ({
  NetworkLatencyPanel: Panel,
}));
vi.mock('./OverviewPage/components/ThroughputPanel', () => ({
  ThroughputPanel: Panel,
}));
vi.mock('./OverviewPage/components/PacketLossPanel', () => ({
  PacketLossPanel: Panel,
}));
vi.mock('./OverviewPage/components/ObstructionGauge', () => ({
  ObstructionGauge: Panel,
}));
vi.mock('./OverviewPage/components/GroundEntryPointPanel', () => ({
  GroundEntryPointPanel: Panel,
}));
vi.mock('./OverviewPage/components/POIQuickReference', () => ({
  POIQuickReference: Panel,
}));

function renderStrict(setItem = vi.fn()) {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem,
      clear: () => store.clear(),
    },
  });
  mocks.useOverviewData.mockReturnValue({
    snapshot: makeOverviewSnapshot(),
    controller: {
      isManualRefreshPending: false,
      manualRefresh: mocks.manualRefresh,
      radarRefreshToken: 7,
      retryRadar: mocks.retryRadar,
      reportRadarResult: mocks.reportRadarResult,
    },
  });
  render(
    <StrictMode>
      <OverviewPage />
    </StrictMode>
  );
}

describe('OverviewPage StrictMode persistence', () => {
  beforeEach(() => {
    mocks.useOverviewData.mockReset();
    mocks.manualRefresh.mockReset();
    mocks.retryRadar.mockReset();
    mocks.reportRadarResult.mockReset();
    mocks.focusCoordinates.mockReset();
  });

  it('persists a cadence action exactly once', () => {
    const setItem = vi.fn();
    renderStrict(setItem);
    fireEvent.click(screen.getByRole('button', { name: 'Overview controls' }));
    setItem.mockClear();
    fireEvent.change(screen.getByLabelText('Refresh cadence'), {
      target: { value: 'paused' },
    });
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(setItem.mock.calls[0][0]).toBe(OVERVIEW_PREFERENCES_STORAGE_KEY);
  });
});
