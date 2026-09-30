import { describe, expect, it } from 'vitest';
import uPlot from 'uplot';
import { OVERVIEW_METRIC_GRAPHS } from './overview-metric-history';
import { metricPlotOptions } from './overview-metric-plot-options';
describe('metricPlotOptions', () => {
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
