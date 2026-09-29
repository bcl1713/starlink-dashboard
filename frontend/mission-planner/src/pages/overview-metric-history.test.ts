import { describe, expect, it } from 'vitest';
import type { OverviewHistoryBundle } from '../services/overview-history';
import { OVERVIEW_METRIC_GRAPHS, projectMetricHistory } from './overview-metric-history';

const metricCases = [
  ['latency', 'starlink_network_latency_ms_current', 'Network latency', 'ms'],
  ['downlink', 'starlink_network_throughput_down_mbps_current', 'Downlink throughput', 'Mbps'],
  ['uplink', 'starlink_network_throughput_up_mbps_current', 'Uplink throughput', 'Mbps'],
  ['packet-loss', 'starlink_network_packet_loss_percent', 'Packet loss', '%'],
  ['obstruction', 'starlink_dish_obstruction_percent', 'Dish obstruction', '%'],
] as const;

function bundle(metric: string): OverviewHistoryBundle {
  return {
    window_seconds: 30,
    start_timestamp_seconds: 90,
    end_timestamp_seconds: 120,
    step_seconds: 5,
    series: { [metric]: [[100, 4], [105, 5], [115, 7]] },
    rolling_5m: {
      [metric]: {
        state: 'available',
        min: [[100, 3], [110, 3], [115, 4]],
        avg: [[100, 4], [110, 4], [115, 6]],
        max: [[100, 5], [110, 6], [115, 8]],
      },
    },
  };
}

describe('overview metric history', () => {
  it.each(metricCases)('maps %s to the shared metric, label and unit', (id, metric, label, unit) => {
    const descriptor = OVERVIEW_METRIC_GRAPHS.find((graph) => graph.id === id);
    expect(descriptor).toEqual({ id, metric, label, unit });
    expect(projectMetricHistory(bundle(metric), descriptor!, 117_500).observed).toEqual([4, 5, null, 7]);
  });

  it('aligns four independent traces at actual timestamps', () => {
    const result = projectMetricHistory(bundle(metricCases[0][1]), OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result).toEqual({
      state: 'available',
      times: [100, 105, 110, 115],
      observed: [4, 5, null, 7],
      min: [3, null, 3, 4],
      avg: [4, null, 4, 6],
      max: [5, null, 6, 8],
      visibleRightSeconds: 110,
    });
  });

  it('reports empty when the selected metric has no samples', () => {
    const response = bundle(metricCases[0][1]);
    response.rolling_5m![metricCases[1][1]] = { state: 'available', min: [], avg: [], max: [] };
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[1], 1_000_000);
    expect(result).toEqual({ state: 'empty', times: [], observed: [], min: [], avg: [], max: [], visibleRightSeconds: 120 });
  });

  it('retains raw samples but marks an unavailable rollup', () => {
    const response = bundle(metricCases[0][1]);
    response.rolling_5m![metricCases[0][1]].state = 'unavailable';
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.state).toBe('unavailable');
    expect(result.observed).toEqual([4, 5, null, 7]);
    expect(result.min).toEqual([null, null, null, null]);
  });

  it('treats missing rolling_5m in older cached bundles as unavailable', () => {
    const response = bundle(metricCases[0][1]);
    delete response.rolling_5m;
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.state).toBe('unavailable');
    expect(result.times).toEqual([100, 105, 110, 115]);
    expect(result.observed).toEqual([4, 5, null, 7]);
  });

  it('drops malformed and non-finite samples rather than turning them into zero', () => {
    const response = bundle(metricCases[0][1]);
    response.series[metricCases[0][1]] = [[100, 4], [105, NaN], [110, Infinity], [115, 7], [NaN, 9], [120] as never, null as never];
    response.rolling_5m![metricCases[0][1]].min = [[100, 3], [Infinity, 1], [115, NaN]];
    response.rolling_5m![metricCases[0][1]].avg = [[105, 9]];
    response.rolling_5m![metricCases[0][1]].max = [];
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.times).toEqual([100, 105, 110, 115]);
    expect(result.observed).toEqual([4, null, null, 7]);
    expect(result.min).toEqual([3, null, null, null]);
  });

  it('inserts a null marker across a stale interval without inventing measurements', () => {
    const response = bundle(metricCases[0][1]);
    response.series[metricCases[0][1]] = [[100, 4], [110, 7]];
    response.rolling_5m![metricCases[0][1]] = { state: 'available', min: [], avg: [], max: [] };
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.times).toEqual([100, 105, 110]);
    expect(result.observed).toEqual([4, null, 7]);
  });

  it('does not connect a missing interval when no finite timestamp fits between samples', () => {
    const response = bundle(metricCases[0][1]);
    response.step_seconds = 1;
    response.series[metricCases[0][1]] = [[1e16, 4], [1e16 + 2, 7]];
    response.rolling_5m![metricCases[0][1]] = { state: 'available', min: [[1e16, 3], [1e16 + 2, 6]], avg: [], max: [] };
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.times).toEqual([1e16, 1e16 + 2]);
    expect(result.observed).toEqual([null, 7]);
    expect(result.min).toEqual([null, 6]);
  });

  it('keeps a finite null gap marker between large positive timestamps', () => {
    const response = bundle(metricCases[0][1]);
    response.step_seconds = 1e306;
    response.series[metricCases[0][1]] = [[1e308, 4], [1.1e308, 7]];
    response.rolling_5m![metricCases[0][1]] = { state: 'available', min: [], avg: [], max: [] };
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.times).toEqual([1e308, 1.05e308, 1.1e308]);
    expect(result.observed).toEqual([4, null, 7]);
  });

  it('keeps separate null gaps across a very long window', () => {
    const response = bundle(metricCases[0][1]);
    response.step_seconds = 1e306;
    response.start_timestamp_seconds = 1e308;
    response.end_timestamp_seconds = 1.6e308;
    response.series[metricCases[0][1]] = [[1e308, 4], [1.3e308, 5], [1.6e308, 7]];
    response.rolling_5m![metricCases[0][1]] = { state: 'available', min: [], avg: [], max: [] };
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 117_500);
    expect(result.times).toEqual([1e308, 1.15e308, 1.3e308, 1.45e308, 1.6e308]);
    expect(result.observed).toEqual([4, null, 5, null, 7]);
    expect(result.times.every(Number.isFinite)).toBe(true);
  });

  it('does not generate future timestamps for an old or empty bundle', () => {
    const response = bundle(metricCases[0][1]);
    response.series = {};
    response.rolling_5m = {};
    const result = projectMetricHistory(response, OVERVIEW_METRIC_GRAPHS[0], 1_000_000);
    expect(result.times).toEqual([]);
    expect(result.visibleRightSeconds).toBe(120);
    expect(result.state).toBe('unavailable');
  });
});
