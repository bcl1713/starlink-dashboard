import { beforeEach, expect, it, vi } from 'vitest';
import {
  overviewLinkSettingsApi,
  overviewPresetsApi,
  OVERVIEW_VISIBILITY_DEFAULTS,
} from './overview-link-settings';
import { overviewWeatherApi } from './overview-weather';
import { aviationWeatherApi } from './aviation-weather';
import {
  applyDisplayPreset,
  saveCurrentDisplayPreset,
} from './overview-preset-actions';
const links = {
  ...OVERVIEW_VISIBILITY_DEFAULTS,
  starshield_link_enabled: true,
  x_band_link_enabled: true,
  orbital_traffic_enabled: false,
  aircraft_history_enabled: true,
  country_borders_enabled: false,
  state_borders_enabled: false,
};
const weather = {
  radar: true,
  metar: false,
  taf: true,
  sigmet: true,
  sigmet_intersecting_only: true,
  winds: true,
  temperature: false,
};
const aviation = {
  ...weather,
  revision: 7,
  gfs_selection: {
    vertical: { kind: 'pressure' as const, pressure_pa: 50000 as const },
    horizon_hours: 6 as const,
  },
};
const preset = { version: 1, settings: links, weather_visibility: weather };
beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(overviewLinkSettingsApi, 'get').mockResolvedValue(links);
  vi.spyOn(overviewWeatherApi, 'getSettings').mockResolvedValue({
    enabled: true,
    revision: 3,
  });
  vi.spyOn(aviationWeatherApi, 'getSettings').mockResolvedValue(aviation);
  vi.spyOn(overviewLinkSettingsApi, 'update').mockResolvedValue(links);
  vi.spyOn(overviewWeatherApi, 'updateSettings').mockResolvedValue({
    enabled: true,
    revision: 3,
  });
  vi.spyOn(aviationWeatherApi, 'updateSettings').mockResolvedValue(aviation);
  vi.spyOn(overviewPresetsApi, 'save').mockResolvedValue(preset);
});
it('saves stable authoritative current visibility without forecast/provider configuration', async () => {
  await saveCurrentDisplayPreset('weather', 0);
  expect(overviewPresetsApi.save).toHaveBeenCalledWith(
    'weather',
    links,
    0,
    weather
  );
  expect(aviationWeatherApi.getSettings).toHaveBeenCalledTimes(2);
  expect(overviewLinkSettingsApi.update).not.toHaveBeenCalled();
});
it('refuses a changing snapshot or unavailable weather instead of saving a partial bundle', async () => {
  vi.mocked(overviewWeatherApi.getSettings).mockResolvedValueOnce({
    enabled: false,
    revision: 2,
  });
  await expect(saveCurrentDisplayPreset('weather', 0)).rejects.toThrow(
    /changed/i
  );
  expect(overviewPresetsApi.save).not.toHaveBeenCalled();
  vi.mocked(overviewWeatherApi.getSettings).mockRejectedValue(
    new Error('Radar unavailable')
  );
  await expect(saveCurrentDisplayPreset('weather', 0)).rejects.toThrow(
    /unavailable/
  );
  expect(overviewPresetsApi.save).not.toHaveBeenCalled();
});
it('applies every visibility store with observed baselines and excludes forecast selection', async () => {
  await expect(applyDisplayPreset(preset)).resolves.toEqual({ legacy: false });
  expect(overviewWeatherApi.updateSettings).toHaveBeenCalledWith({
    enabled: true,
    expected_revision: 3,
  });
  const aviationVisibility = {
    metar: weather.metar,
    taf: weather.taf,
    sigmet: weather.sigmet,
    sigmet_intersecting_only: weather.sigmet_intersecting_only,
    winds: weather.winds,
    temperature: weather.temperature,
  };
  expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
    ...aviationVisibility,
    expected_revision: 7,
  });
  expect(overviewLinkSettingsApi.update).toHaveBeenCalledWith(links, links);
});
it('reports partial acknowledgment accurately and supports a fresh-baseline retry', async () => {
  vi.mocked(aviationWeatherApi.updateSettings).mockRejectedValueOnce(
    new Error('Revision conflict')
  );
  await expect(applyDisplayPreset(preset)).rejects.toThrow(
    /Confirmed: Panels and map, Radar.*Unconfirmed: Aviation weather/
  );
  await expect(applyDisplayPreset(preset)).resolves.toEqual({ legacy: false });
});
it('does not change any store if preflight cannot read weather; labels legacy presets', async () => {
  vi.mocked(overviewWeatherApi.getSettings).mockRejectedValue(
    new Error('Unavailable')
  );
  await expect(applyDisplayPreset(preset)).rejects.toThrow('Unavailable');
  expect(overviewLinkSettingsApi.update).not.toHaveBeenCalled();
  await expect(
    applyDisplayPreset({ version: 1, settings: links })
  ).resolves.toEqual({ legacy: true });
  expect(overviewWeatherApi.updateSettings).not.toHaveBeenCalled();
});

it('does not confirm a full save or apply from an acknowledgment omitting requested visibility', async () => {
  vi.mocked(overviewPresetsApi.save).mockResolvedValue({
    version: 1,
    settings: links,
  });
  await expect(saveCurrentDisplayPreset('weather', 0)).rejects.toThrow(
    /acknowledgment/i
  );
  vi.mocked(overviewWeatherApi.updateSettings).mockResolvedValue({
    enabled: false,
    revision: 4,
  });
  await expect(applyDisplayPreset(preset)).rejects.toThrow(
    /Unconfirmed: Radar/
  );
});
