import { describe, expect, it } from 'vitest';
import uPlot from 'uplot';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import {
  metricPlotData,
  metricPlotOptions,
} from './overview-metric-plot-options';
describe('metricPlotOptions', () => {
  it.each(OVERVIEW_METRIC_GRAPHS.slice(3))(
    'uses a base-10 logarithmic scale for $id with zeros at the baseline',
    (descriptor) => {
      const options = metricPlotOptions({
        width: 600,
        height: 80,
        yRange: { min: 1, max: 100 },
        descriptor,
      });
      expect(options.scales!.y).toMatchObject({ distr: 3, log: 10 });
      const clamp = options.scales!.y!.clamp;
      expect(clamp).toBeTypeOf('function');
      if (typeof clamp === 'function')
        expect(clamp({} as uPlot, 0, 1, 100, 'y')).toBe(1);
    }
  );
  it.each(OVERVIEW_METRIC_GRAPHS.slice(3))(
    'keeps all $id traces visible below the log floor without changing source values or gaps',
    (descriptor) => {
      const projection = {
        state: 'available' as const,
        times: [100, 105, 110, 115],
        max: [0, 0.005, null, 100],
        min: [0, 0.001, null, 0.1],
        avg: [0, 0.003, null, 1],
        observed: [0, 0.004, null, 10],
      };
      expect(metricPlotData(descriptor, projection)).toEqual([
        [100, 105, 110, 115],
        [1, 1, null, 100],
        [1, 1, null, 1],
        [1, 1, null, 1],
        [1, 1, null, 10],
      ]);
      expect(projection.observed).toEqual([0, 0.004, null, 10]);
      expect(projection.min).toEqual([0, 0.001, null, 0.1]);
    }
  );
  it.each(OVERVIEW_METRIC_GRAPHS.slice(0, 3))(
    'retains the linear scale and original values for $id',
    (descriptor) => {
      const options = metricPlotOptions({
        width: 600,
        height: 80,
        yRange: { min: 0, max: 100 },
        descriptor,
      });
      expect(options.scales!.y!.distr ?? 1).toBe(1);
      const projection = {
        state: 'available' as const,
        times: [100, 105],
        max: [0, null],
        min: [0, null],
        avg: [0, null],
        observed: [0.004, null],
      };
      expect(metricPlotData(descriptor, projection)).toEqual([
        [100, 105],
        [0, null],
        [0, null],
        [0, null],
        [0.004, null],
      ]);
    }
  );
  it('emits one envelope with quiet average and prominent observed trace on a plot-only host', () => {
    const options = metricPlotOptions({
      width: 600,
      height: 80,
      yRange: { min: 0, max: 10 },
      descriptor: OVERVIEW_METRIC_GRAPHS[0],
    });
    expect(options.series).toHaveLength(5);
    expect(options.bands).toEqual([
      { series: [1, 2], fill: 'rgba(180, 195, 215, 0.14)' },
    ]);
    expect(options.series.slice(1).map((s) => s.label)).toEqual([
      'High',
      'Low',
      'Average',
      'Observed',
    ]);
    for (const edge of options.series.slice(1, 3))
      expect(edge).toMatchObject({
        show: true,
        stroke: 'transparent',
        width: 0,
      });
    expect(options.series[3]).toMatchObject({
      stroke: '#e2e8f0',
      width: 1.25,
      dash: [5, 4],
    });
    expect(options.series[4]).toMatchObject({ stroke: '#67e8f9', width: 2.25 });
    for (const series of options.series.slice(1))
      expect(series).toMatchObject({
        spanGaps: false,
        points: { show: false },
      });
    expect(options.cursor).toEqual({ show: false });
    expect(options.legend).toEqual({ show: false });
    expect(options.axes).toEqual([{ show: false }, { show: false }]);
    expect(options.scales!.x!.range).toBeTypeOf('function');
    expect(options.scales!.y!.range).toBeTypeOf('function');
    const x = options.scales!.x!.range as uPlot.Scale.Range;
    const y = options.scales!.y!.range as uPlot.Scale.Range;
    if (typeof x === 'function' && typeof y === 'function') {
      expect(x({} as uPlot, 100, 130, 'x')).toEqual([100, 130]);
      expect(y({} as uPlot, 0, 30, 'y')).toEqual([0, 30]);
    }
  });
});
