export function readyWeather() {
  return {
    state: 'ready' as const,
    settings_revision: 1,
    generated_at_ms: 1791244800000,
    frame_time_ms: 1791244200000,
    coverage_token: 20732,
    coverage_expires_at_ms: 1791331200000,
    zoom: 2 as const,
    tile_size: 512 as const,
    radar_tile_template:
      '/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png',
    coverage_tile_template:
      '/api/overview-weather/coverage/20732/{z}/{x}/{y}.png',
  };
}
