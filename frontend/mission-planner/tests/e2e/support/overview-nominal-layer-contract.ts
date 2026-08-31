export const NOMINAL_FEATURE_COUNTS = [
  1, 1, 1, 1, 1, 1, 0, 2, 1, 2, 1, 1,
] as const;

export const NOMINAL_CHART_SERIES_COUNTS = [1, 1, 2] as const;

export function nominalLayerSummaryPattern(
  label: string,
  index: number
): RegExp {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(
    `${escaped}: visible,.*${NOMINAL_FEATURE_COUNTS[index]} features`,
    'i'
  );
}
