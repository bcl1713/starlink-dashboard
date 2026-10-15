export function readyWeather() {
  return {
    state: 'ready' as const,
    settings_revision: 1,
    generated_at_ms: 1791244800000,
    frame_time_ms: 1791244200000,
    coverage_token: 20732,
    coverage_expires_at_ms: 1791331200000,
    source: 'rainviewer',
    provenance: 'RainViewer observed radar',
    product: 'observed-precipitation' as const,
    product_id: 'a'.repeat(64),
    tile_schema: 'xyz-rgba-pair-v1' as const,
    coverage_encoding: 'absence-rgba-v1' as const,
    max_zoom: 7,
    attribution: { label: 'RainViewer', url: 'https://www.rainviewer.com/' },
    zoom: 2 as const,
    tile_size: 512 as const,
    radar_tile_template:
      '/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png?product_id=' +
      'a'.repeat(64),
    coverage_tile_template:
      '/api/overview-weather/coverage/20732/{z}/{x}/{y}.png?product_id=' +
      'a'.repeat(64),
  };
}
