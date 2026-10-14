/** Shared sRGB palette: renderer uniforms and legend use identical stops. */
export const WIND_COLOR_STOPS = Object.freeze(
  [
    { knots: 0, hex: '#1d4ed8' },
    { knots: 25, hex: '#06b6d4' },
    { knots: 50, hex: '#22c55e' },
    { knots: 75, hex: '#eab308' },
    { knots: 100, hex: '#f97316' },
    { knots: 125, hex: '#ef4444' },
    { knots: 150, hex: '#a855f7' },
  ].map((stop) => Object.freeze(stop))
);

export const windSpeedKnots = (u: number, v: number): number =>
  Math.hypot(u, v) * 1.9438444924406;

function rgb(hex: string): readonly [number, number, number] {
  const n = Number.parseInt(hex.slice(1), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}
export function windColor(knots: number): readonly [number, number, number] {
  for (let i = 1; i < WIND_COLOR_STOPS.length; i++) {
    const a = WIND_COLOR_STOPS[i - 1],
      b = WIND_COLOR_STOPS[i];
    if (knots === b.knots) return rgb(b.hex);
    if (knots <= b.knots) {
      const f = Math.max(0, (knots - a.knots) / (b.knots - a.knots));
      const x = rgb(a.hex),
        y = rgb(b.hex);
      return [
        x[0] + (y[0] - x[0]) * f,
        x[1] + (y[1] - x[1]) * f,
        x[2] + (y[2] - x[2]) * f,
      ];
    }
  }
  return rgb(WIND_COLOR_STOPS[WIND_COLOR_STOPS.length - 1].hex);
}
export function windLegendGradient(): string {
  return `linear-gradient(to right, ${WIND_COLOR_STOPS.map((s) => `${s.hex} ${(s.knots / 150) * 100}%`).join(', ')})`;
}
