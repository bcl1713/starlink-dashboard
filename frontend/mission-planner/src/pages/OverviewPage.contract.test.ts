import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(
  new URL('./OverviewPage.tsx', import.meta.url),
  'utf8'
);

describe('OverviewPage generated POI legend and overlay layout contracts', () => {
  it('shares status and confirmed settings while preserving aircraft, X-band and shared history consumers', () => {
    expect(pageSource).toMatch(
      /<OverviewMetricHistoryPanels[\s\S]*?status=\{status\}[\s\S]*?statusError=\{Boolean\(statusError\)\}/
    );
    expect(pageSource.match(/\buseStatus\(\)/g)).toHaveLength(1);
    expect(pageSource.match(/\buseOverviewHistory\(\)/g)).toHaveLength(1);
    expect(pageSource.match(/\buseOverviewLinkSettings\(true\)/g)).toHaveLength(
      1
    );
    expect(pageSource).toMatch(
      /projectAircraftHistory\(\s*overviewHistory\?\.series \?\? \{\},/
    );
    expect(pageSource).not.toContain('OverviewMetricsPanel');
  });
  it('describes generated POI urgency without obsolete fixed route endpoint entries', () => {
    expect(pageSource).not.toContain('<span>Origin</span>');
    expect(pageSource).not.toContain('<span>Destination</span>');
    expect(pageSource).not.toContain('globe-legend__marker--origin');
    expect(pageSource).not.toContain('globe-legend__marker--destination');
    expect(pageSource).toContain('aria-label="Map POIs"');
  });
});
