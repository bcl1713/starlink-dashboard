/** Presentation only: source values, history and domains retain full precision. */
export function formatMetricValue(value: number, unit: string): string {
  if (!Number.isFinite(value)) return 'Unavailable';
  const decimals = unit === 'ms' ? 0 : unit === 'Mbps' ? 1 : 2;
  const increment = 10 ** -decimals;
  const suffix = unit === '%' ? '%' : ` ${unit}`;
  if (value !== 0 && Math.abs(value) < increment) {
    return value > 0 ? `<${increment}${suffix}` : `>-${increment}${suffix}`;
  }
  const number =
    Math.abs(value) >= 10_000
      ? value.toExponential(decimals)
      : String(Number(value.toFixed(decimals)));
  return `${number}${suffix}`;
}

/** Remove binary tails, retaining meaningful fractional scale boundaries. */
export function formatMetricAxis(value: number): string {
  return String(Number(value.toPrecision(12)));
}
