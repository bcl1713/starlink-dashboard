import {
  overviewLinkSettingsApi,
  overviewPresetsApi,
  type OverviewPreset,
  type OverviewPresetName,
  type OverviewLinkSettingsUpdate,
} from './overview-link-settings';
import { overviewWeatherApi } from './overview-weather';
import { aviationWeatherApi } from './aviation-weather';
import { presetWeatherSchema } from './overview-preset-weather';

function confirmFields(expected: object, actual: object) {
  if (
    Object.entries(expected).some(
      ([key, value]) => (actual as Record<string, unknown>)[key] !== value
    )
  )
    throw new Error(
      'Settings acknowledgment did not confirm requested visibility'
    );
}
async function readDisplay() {
  const [links, radar, aviation] = await Promise.all([
    overviewLinkSettingsApi.get(),
    overviewWeatherApi.getSettings(),
    aviationWeatherApi.getSettings(),
  ]);
  return { links, radar, aviation };
}
/** A stable observed snapshot, not an atomic transaction across independent stores. */
export async function saveCurrentDisplayPreset(
  name: OverviewPresetName,
  version: number
) {
  const current = await readDisplay();
  const confirmed = await readDisplay();
  if (
    current.radar.revision !== confirmed.radar.revision ||
    current.aviation.revision !== confirmed.aviation.revision ||
    Object.entries(current.links).some(
      ([key, value]) =>
        confirmed.links[key as keyof typeof confirmed.links] !== value
    )
  )
    throw new Error(
      'Display settings changed while capturing the preset; review and retry.'
    );
  const { metar, taf, sigmet, sigmet_intersecting_only, winds, temperature } =
    current.aviation;
  const weather = presetWeatherSchema.parse({
    radar: current.radar.enabled,
    metar,
    taf,
    departure_weather: current.aviation.departure_weather ?? false,
    arrival_weather: current.aviation.arrival_weather ?? false,
    sigmet,
    sigmet_intersecting_only,
    winds,
    temperature,
  });
  const saved = await overviewPresetsApi.save(
    name,
    current.links,
    version,
    weather
  );
  if (!saved.weather_visibility)
    throw new Error('Preset acknowledgment omitted weather visibility');
  confirmFields(weather, saved.weather_visibility);
  confirmFields(current.links, saved.settings);
  return saved;
}
function baseline(
  settings: OverviewLinkSettingsUpdate,
  current: OverviewLinkSettingsUpdate
) {
  return Object.fromEntries(
    Object.keys(settings).map((key) => [
      key,
      current[key as keyof typeof current],
    ])
  );
}
export async function applyDisplayPreset(
  preset: OverviewPreset
): Promise<{ legacy: boolean }> {
  const settings = { next_flight_events_only: false, ...preset.settings };
  if (!preset.weather_visibility) {
    const current = await overviewLinkSettingsApi.get();
    const saved = await overviewLinkSettingsApi.update(
      settings,
      baseline(settings, current)
    );
    confirmFields(settings, saved);
    return { legacy: true };
  }
  const weather = presetWeatherSchema.parse(preset.weather_visibility);
  const current = await readDisplay();
  const { radar, ...aviation } = weather;
  const operations = [
    {
      name: 'Panels and map',
      save: () =>
        overviewLinkSettingsApi
          .update(settings, baseline(settings, current.links))
          .then((saved) => confirmFields(settings, saved)),
    },
    {
      name: 'Radar',
      save: () =>
        overviewWeatherApi
          .updateSettings({
            enabled: radar,
            expected_revision: current.radar.revision,
          })
          .then((saved) => confirmFields({ enabled: radar }, saved)),
    },
    {
      name: 'Aviation weather',
      save: () =>
        aviationWeatherApi
          .updateSettings({
            ...aviation,
            expected_revision: current.aviation.revision,
          })
          .then((saved) => confirmFields(aviation, saved)),
    },
  ];
  const results = await Promise.allSettled(
    operations.map((item) => item.save())
  );
  const confirmed = operations
    .filter((_, index) => results[index].status === 'fulfilled')
    .map((item) => item.name);
  const unconfirmed = operations.flatMap((item, index) => {
    const result = results[index];
    return result.status === 'rejected'
      ? [
          `${item.name} (${result.reason instanceof Error ? result.reason.message : 'save unavailable'})`,
        ]
      : [];
  });
  if (unconfirmed.length)
    throw new Error(
      `Preset application incomplete. Confirmed: ${confirmed.join(', ') || 'none'}. Unconfirmed: ${unconfirmed.join(', ')}. Refresh settings and apply again to retry.`
    );
  return { legacy: false };
}
