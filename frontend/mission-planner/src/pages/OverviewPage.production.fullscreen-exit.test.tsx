import { fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  finishOverviewProductionCycle,
  getOverviewProductionMocks,
  installOverviewProductionBrowser,
  renderWithOverviewClient,
  resolveOverviewProductionServices,
} from './OverviewPage/production-test-harness';
import { OverviewPage } from './OverviewPage';

const mocks = getOverviewProductionMocks();

describe('OverviewPage native fullscreen exit rejection', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-08-31T05:00:00.000Z'));
    installOverviewProductionBrowser();
    resolveOverviewProductionServices();
    mocks.createdPlots.length = 0;
    Object.values(mocks).forEach((value) => {
      if (typeof value === 'function' && 'mockClear' in value)
        value.mockClear();
    });
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: vi.fn(() => null), setItem: vi.fn() },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps native state after rejected exit click and retries until fullscreenchange exits', async () => {
    const { container } = renderWithOverviewClient(<OverviewPage />);
    await finishOverviewProductionCycle();
    const page = container.querySelector('.overview-page') as HTMLElement;
    const exitFullscreen = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error('exit blocked'))
      .mockResolvedValueOnce(undefined);
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: page,
    });
    fireEvent(document, new Event('fullscreenchange'));
    expect(page).toHaveClass('overview-page--native');
    const focus = vi.spyOn(HTMLButtonElement.prototype, 'focus');

    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen' }));
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    expect(page).toHaveClass('overview-page--native');
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
    expect(focus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Exit fullscreen' }));
    expect(exitFullscreen).toHaveBeenCalledTimes(2);
    await Promise.resolve();
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      value: null,
    });
    fireEvent(document, new Event('fullscreenchange'));
    expect(page).toHaveClass('overview-page--inline');
    expect(
      screen.getByRole('button', { name: 'Enter fullscreen' })
    ).toHaveFocus();
    expect(focus).toHaveBeenCalledTimes(1);
  }, 20_000);
});
