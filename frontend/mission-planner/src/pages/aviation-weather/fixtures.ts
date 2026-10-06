// Deterministic, normalized contract fixtures for focused weather tests.
export const NOW = Date.parse('2026-10-06T12:00:00Z');
export const weatherValues = {
  wind_direction_deg: null,
  wind_variable: true,
  wind_speed_mps: 5,
  gust_mps: null,
  visibility_m: 10000,
  visibility_lower_bound: true,
  ceiling_m: null,
  ceiling_known: true,
  weather_codes: [],
};
export function station(taf = false) {
  return {
    type: 'Feature',
    id: 'test-station',
    geometry: { type: 'Point', coordinates: [0, 0] },
    properties: {
      station_id: 'TEST',
      report_type: taf ? 'TAF' : 'METAR',
      raw_text: 'TEST report',
      observed_at_ms: taf ? null : NOW - 60000,
      issued_at_ms: taf ? NOW - 60000 : null,
      valid_from_ms: taf ? NOW : null,
      valid_to_ms: taf ? NOW + 3600000 : null,
      ...weatherValues,
      ceiling_reference: 'AGL',
      pressure_pa: null,
      temperature_k: 280,
      dewpoint_k: null,
      flight_category: 'VFR',
      fresh_until_ms: NOW + 60000,
      expires_at_ms: NOW + 3600000,
      forecast_groups: taf
        ? [
            {
              change_type: null,
              probability: null,
              time_becoming_ms: null,
              valid_from_ms: NOW,
              valid_to_ms: NOW + 3600000,
              ...weatherValues,
            },
          ]
        : [],
    },
  };
}
export function advisory() {
  return {
    type: 'Feature',
    id: 'test-advisory',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [4, 0],
          [4, 4],
          [0, 4],
          [0, 0],
        ],
        [
          [1, 1],
          [1, 3],
          [3, 3],
          [3, 1],
          [1, 1],
        ],
      ],
    },
    properties: {
      issuer: 'TEST',
      fir: 'TEST',
      series: '1',
      bulletin_series: '1',
      cancellation_target: null,
      revision: null,
      phenomenon: 'TURB',
      severity: 'SEV',
      raw_text: 'TEST SIGMET',
      issued_at_ms: null,
      valid_from_ms: NOW,
      valid_to_ms: NOW + 3600000,
      expires_at_ms: NOW + 3600000,
      vertical: {
        lower: null,
        upper: null,
        unit: 'unknown',
        reference: 'unknown',
      },
      cancelled: false,
      amends: null,
    },
  };
}
export const collection = (features: unknown[]) => ({
  type: 'FeatureCollection',
  source_id: 'awc',
  retrieved_at_ms: NOW,
  feed_completeness: 'unknown',
  omitted_features: 0,
  features,
});
