import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(
  new URL('./OverviewPage.tsx', import.meta.url),
  'utf8'
);
const styles = readFileSync(
  new URL('./OverviewPage.css', import.meta.url),
  'utf8'
);

describe('OverviewPage generated POI legend and overlay layout contracts', () => {
  it('shares status with network panels while preserving aircraft, X-band and shared history consumers', () => {
    expect(pageSource).toMatch(
      /<OverviewMetricHistoryPanels[\s\S]*?status=\{status\}[\s\S]*?statusError=\{Boolean\(statusError\)\}/
    );
    expect(pageSource.match(/\buseStatus\(\)/g)).toHaveLength(1);
    expect(pageSource.match(/\buseOverviewHistory\(\)/g)).toHaveLength(1);
    expect(pageSource).toContain('projectAircraftPosition(status ?? {})');
    expect(pageSource).toMatch(/projectConfiguredXBandActiveLink\(\s*status,/);
    expect(pageSource).toMatch(
      /projectAircraftHistory\(\s*overviewHistory\?\.series \?\? \{\},/
    );
    expect(pageSource).not.toContain('OverviewMetricsPanel');
  });
  it('reserves a structural left stack for history graphs before Upcoming POIs', () => {
    expect(pageSource).toMatch(
      /<div className="overview-left-stack">[\s\S]*?<OverviewMetricHistoryPanels[\s\S]*?<UpcomingPoisPanel/
    );
    expect(pageSource).toContain('history={overviewHistory}');
    expect(pageSource).toContain('error={isOverviewHistoryError}');
    expect(styles).toMatch(
      /\.overview-left-stack \{[\s\S]*?display: (?:flex|grid);/
    );
    expect(styles).toMatch(
      /\.overview-metric-history-panels \{[\s\S]*?display: (?:flex|grid);/
    );
  });
  it('describes generated POI urgency without obsolete fixed route endpoint entries', () => {
    expect(pageSource).not.toContain('<span>Origin</span>');
    expect(pageSource).not.toContain('<span>Destination</span>');
    expect(pageSource).not.toContain('globe-legend__marker--origin');
    expect(pageSource).not.toContain('globe-legend__marker--destination');
    expect(pageSource).toContain('<span>Generated POIs</span>');
    expect(pageSource).toContain('Colour indicates estimated arrival urgency');
  });

  it('keeps the POI panel clear of the bottom-right legend at narrow widths', () => {
    expect(styles).toMatch(
      /@media \(max-width: 70rem\), \(max-height: 60rem\) \{[\s\S]*?\.overview-metric-history-panels \{[\s\S]*?grid-template-columns: minmax\(0, 1fr\);/
    );
    expect(styles).toMatch(
      /@media \(max-width: 70rem\), \(max-height: 60rem\) \{[\s\S]*?\.overview-page \{[\s\S]*?overflow-y: auto;/
    );
    expect(styles).toMatch(
      /@media \(max-width: 70rem\), \(max-height: 60rem\) \{[\s\S]*?\.globe-legend,[\s\S]*?\.overview-bottom-overlays \{[\s\S]*?position: relative;[\s\S]*?width: auto;/
    );
    expect(styles).toMatch(
      /\.overview-bottom-overlays \{[\s\S]*?pointer-events: none;/
    );
  });

  it('places the fullscreen control in reserved normal flow beside narrow POI states', () => {
    expect(styles).toMatch(
      /@media \(max-width: 70rem\), \(max-height: 60rem\) \{[\s\S]*?\.overview-fullscreen-control \{[\s\S]*?position: relative;[\s\S]*?bottom: auto;[\s\S]*?left: auto;[\s\S]*?margin: 1rem;/
    );
    expect(styles).toMatch(
      /@media \(max-width: 70rem\), \(max-height: 60rem\) \{[\s\S]*?\.overview-bottom-overlays \{[\s\S]*?position: relative;/
    );
  });
});
