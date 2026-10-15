import { expect, it } from 'vitest';

async function scale() {
  const modulePath = './wind-scale';
  return import(modulePath);
}
it('uses the fixed knots stops and exact unrounded SI conversion', async () => {
  const { WIND_COLOR_STOPS, windSpeedKnots } = await scale();
  expect(WIND_COLOR_STOPS).toEqual([
    { knots: 0, hex: '#1d4ed8' },
    { knots: 25, hex: '#06b6d4' },
    { knots: 50, hex: '#22c55e' },
    { knots: 75, hex: '#eab308' },
    { knots: 100, hex: '#f97316' },
    { knots: 125, hex: '#ef4444' },
    { knots: 150, hex: '#a855f7' },
  ]);
  expect(windSpeedKnots(3, 4)).toBeCloseTo(9.719222462203, 12);
  expect(windSpeedKnots(250 / 1.9438444924406, 0)).toBeCloseTo(250, 12);
});
it('interpolates sRGB while saturating only displayed color', async () => {
  const { windColor, windLegendGradient } = await scale();
  expect(windColor(0)).toEqual([29 / 255, 78 / 255, 216 / 255]);
  const midpoint = [(29 + 6) / 510, (78 + 182) / 510, (216 + 212) / 510];
  windColor(12.5).forEach((value: number, i: number) =>
    expect(value).toBeCloseTo(midpoint[i], 14)
  );
  expect(windColor(250)).toEqual(windColor(150));
  expect(windLegendGradient()).toContain('#a855f7 100%');
  expect(windLegendGradient()).toContain('#22c55e');
});
