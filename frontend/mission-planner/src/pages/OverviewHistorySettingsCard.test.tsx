/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('@/hooks/api/useOverviewHistorySettings', () => ({
  useOverviewHistorySettings: vi.fn(),
}));
vi.mock('@/hooks/api/useUpdateOverviewHistorySettings', () => ({
  useUpdateOverviewHistorySettings: vi.fn(),
}));
import { useOverviewHistorySettings } from '@/hooks/api/useOverviewHistorySettings';
import { useUpdateOverviewHistorySettings } from '@/hooks/api/useUpdateOverviewHistorySettings';
import { OverviewHistorySettingsCard } from './OverviewHistorySettingsCard';
afterEach(cleanup);
beforeEach(() => {
  vi.mocked(useOverviewHistorySettings).mockReturnValue({
    data: { window_seconds: 1200 },
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useUpdateOverviewHistorySettings).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as never);
});
describe('persisted Overview history settings', () => {
  it('retains custom durations and saves the chosen shared window', () => {
    const mutate = vi.fn();
    vi.mocked(useUpdateOverviewHistorySettings).mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as never);
    render(<OverviewHistorySettingsCard />);
    const select = screen.getByLabelText(
      'Overview history window'
    ) as HTMLSelectElement;
    expect(select.value).toBe('1200');
    expect(Array.from(select.options, (option) => option.value)).toEqual([
      '1200',
      '300',
      '900',
      '1800',
      '3600',
    ]);
    fireEvent.change(select, { target: { value: '900' } });
    expect(mutate).toHaveBeenCalledExactlyOnceWith(900);
  });
  it.each([
    { isLoading: true, isError: false },
    { isLoading: false, isError: true },
  ])('disables unavailable settings %j', (state) => {
    vi.mocked(useOverviewHistorySettings).mockReturnValue({
      data: undefined,
      ...state,
    } as never);
    render(<OverviewHistorySettingsCard />);
    expect(
      (screen.getByLabelText('Overview history window') as HTMLSelectElement)
        .disabled
    ).toBe(true);
    expect(
      screen.getByRole(state.isError ? 'alert' : 'status').textContent
    ).toContain(state.isError ? 'unavailable' : 'Loading');
  });
  it('distinguishes failed saves from loaded settings and allows retry', () => {
    vi.mocked(useUpdateOverviewHistorySettings).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: true,
    } as never);
    render(<OverviewHistorySettingsCard />);
    expect(screen.getByRole('alert').textContent).toContain('Unable to save');
    expect(
      (screen.getByLabelText('Overview history window') as HTMLSelectElement)
        .disabled
    ).toBe(false);
  });
  it('blocks overlapping edits during a save', () => {
    vi.mocked(useUpdateOverviewHistorySettings).mockReturnValue({
      mutate: vi.fn(),
      isPending: true,
      isError: false,
    } as never);
    render(<OverviewHistorySettingsCard />);
    expect(
      (screen.getByLabelText('Overview history window') as HTMLSelectElement)
        .disabled
    ).toBe(true);
  });
});
