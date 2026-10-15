import type { AviationAdvisory } from '@/services/aviation-features';

/** Prefer canonical bulletin identity; provider variants must not change the label. */
export function sigmetReportLabel(
  reports: readonly AviationAdvisory[]
): string {
  const canonical = reports.filter(
    (report) => report.properties.bulletin_series
  );
  return (
    (canonical.length ? canonical : reports)
      .map(
        ({ properties: p }) =>
          `${p.issuer ?? 'Unknown issuer'} ${p.bulletin_series ?? p.series ?? 'unknown series'}`
      )
      .sort((a, b) => a.localeCompare(b))[0] ?? 'SIGMET report unavailable'
  );
}
