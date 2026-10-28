import type { RunConfig } from './metrics';
export function measurementSeries(
  base: Omit<RunConfig, 'mode'>,
  diagnostic: boolean
): RunConfig[] {
  const normalized = {
    ...base,
    settings: { ...base.settings, view: 'final' as const },
  };
  if (diagnostic)
    return [
      { ...normalized, mode: 'output' },
      {
        ...normalized,
        mode: 'bloom',
        settings: { ...normalized.settings, maxDimension: 480 },
      },
      {
        ...normalized,
        mode: 'bloom',
        settings: { ...normalized.settings, maxDimension: 1920 },
      },
    ];
  return Array.from({ length: 3 }, () =>
    ['current', 'bloom', 'current'].map((mode) => ({
      ...normalized,
      mode: mode as RunConfig['mode'],
    }))
  ).flat();
}
