import { describe, expect, it, vi } from 'vitest';
import apiClient from './api-client';
import {
  overviewHistoryApi,
  overviewHistorySettingsApi,
} from './overview-history';
vi.mock('./api-client', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));
describe('overviewHistoryApi', () => {
  it('gets the shared overview telemetry-history bundle', async () => {
    const bundle = {
      window_seconds: 1800,
      start_timestamp_seconds: 1_781_998_200,
      end_timestamp_seconds: 1_782_000_000,
      step_seconds: 1,
      series: {
        starlink_dish_latitude_degrees: [[1_782_000_000, 41.2566]],
      },
    };
    vi.mocked(apiClient.get).mockResolvedValue({
      data: bundle,
    } as never);
    await expect(overviewHistoryApi.get()).resolves.toEqual(bundle);
    expect(apiClient.get).toHaveBeenCalledWith('/api/overview-history');
  });
  it('gets the persisted overview history window', async () => {
    const settings = {
      window_seconds: 1800,
    };
    vi.mocked(apiClient.get).mockResolvedValue({
      data: settings,
    } as never);
    await expect(overviewHistorySettingsApi.get()).resolves.toEqual(settings);
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/overview-history/settings'
    );
  });
  it('persists a selected overview history window', async () => {
    const settings = {
      window_seconds: 900,
    };
    vi.mocked(apiClient.put).mockResolvedValue({
      data: settings,
    } as never);
    await expect(
      overviewHistorySettingsApi.update(settings.window_seconds)
    ).resolves.toEqual(settings);
    expect(apiClient.put).toHaveBeenCalledWith(
      '/api/overview-history/settings',
      {
        window_seconds: 900,
      }
    );
  });
});
