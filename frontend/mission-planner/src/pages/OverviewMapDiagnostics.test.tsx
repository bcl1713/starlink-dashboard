/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
vi.mock('@/hooks/api/useStatus', () => ({ useStatus: vi.fn() }));
vi.mock('@/hooks/api/useOverviewHistory', () => ({
  useOverviewHistory: vi.fn(),
}));
vi.mock('@/hooks/api/useSatellites', () => ({ useSatellites: vi.fn() }));
vi.mock('@/hooks/api/useActiveXLink', () => ({ useActiveXLink: vi.fn() }));
vi.mock('@/hooks/useCurrentTime', () => ({
  useCurrentTime: () => Date.parse('2026-10-02T00:00:00Z'),
}));
import { useStatus } from '@/hooks/api/useStatus';
import { useOverviewHistory } from '@/hooks/api/useOverviewHistory';
import { useSatellites } from '@/hooks/api/useSatellites';
import { useActiveXLink } from '@/hooks/api/useActiveXLink';
import { OverviewMapDiagnostics } from './OverviewMapDiagnostics';
afterEach(cleanup);
beforeEach(() => {
  vi.mocked(useStatus).mockReturnValue({
    data: {
      timestamp: '2026-10-02T00:00:00Z',
      position: { latitude: 0, longitude: 0, altitude: 35000 },
    },
    isLoading: false,
    error: null,
  } as never);
  vi.mocked(useOverviewHistory).mockReturnValue({
    data: { series: {} },
    isLoading: false,
    isError: false,
  } as never);
  vi.mocked(useSatellites).mockReturnValue({
    data: [
      { satellite_id: 'X-6', transport: 'X', longitude: 0 },
      { satellite_id: 'invalid', transport: 'Ka', longitude: 0 },
    ],
    isLoading: false,
    error: null,
  } as never);
  vi.mocked(useActiveXLink).mockReturnValue({
    data: { satellite_id: 'X-6', state: 'warning' },
    isLoading: false,
    error: null,
  } as never);
});
describe('relocated map diagnostics', () => {
  it('retains configuration counts, planning selection, look angles and supported warning', () => {
    render(<OverviewMapDiagnostics />);
    const region = screen.getByRole('region', {
      name: 'Overview map diagnostics',
    });
    expect(region.textContent).toContain('1 configured satellite');
    expect(region.textContent).toContain('X-6');
    expect(region.textContent).toContain('azimuth 0.0°, elevation 90.0°');
    expect(region.textContent).toContain('Planned link warning');
    expect(region.textContent).toContain('No aircraft history');
    expect(region.textContent).toContain('GEP unavailable');
  });
  it('does not fabricate geometry for an unknown selection', () => {
    vi.mocked(useActiveXLink).mockReturnValue({
      data: { satellite_id: 'missing' },
      isLoading: false,
      error: null,
    } as never);
    render(<OverviewMapDiagnostics />);
    expect(
      screen.getByText('Configured GEO geometry unavailable')
    ).not.toBeNull();
  });
  it('shows failures and retained status as last known', () => {
    vi.mocked(useStatus).mockReturnValue({
      data: {
        timestamp: '2026-10-01T00:00:00Z',
        position: { latitude: 0, longitude: 0, altitude: 0 },
      },
      isLoading: false,
      error: new Error(),
    } as never);
    vi.mocked(useSatellites).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error(),
    } as never);
    vi.mocked(useOverviewHistory).mockReturnValue({
      data: { series: {} },
      isLoading: false,
      isError: true,
    } as never);
    vi.mocked(useActiveXLink).mockReturnValue({
      data: { satellite_id: 'X-6', state: 'warning' },
      isLoading: false,
      error: new Error(),
    } as never);
    render(<OverviewMapDiagnostics />);
    expect(
      screen.getByText('Status refresh unavailable · last known')
    ).not.toBeNull();
    expect(
      screen.getByText('Satellite configuration unavailable')
    ).not.toBeNull();
    expect(screen.getByText('Aircraft history unavailable')).not.toBeNull();
    expect(screen.getByText('Satellite selection unavailable')).not.toBeNull();
    expect(screen.getByText('Last-known planned link warning')).not.toBeNull();
  });
  it('retains loading diagnostics', () => {
    vi.mocked(useOverviewHistory).mockReturnValue({
      isLoading: true,
      isError: false,
    } as never);
    vi.mocked(useSatellites).mockReturnValue({
      isLoading: true,
      error: null,
    } as never);
    render(<OverviewMapDiagnostics />);
    expect(screen.getByText('Loading aircraft history…')).not.toBeNull();
    expect(screen.getByText('Loading satellite configuration…')).not.toBeNull();
  });
});
