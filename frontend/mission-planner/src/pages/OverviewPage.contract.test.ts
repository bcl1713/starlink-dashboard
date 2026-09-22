import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(new URL('./OverviewPage.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('./OverviewPage.css', import.meta.url), 'utf8');

describe('OverviewPage generated POI legend and overlay layout contracts', () => {
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
      /@media \(max-width: 50rem\) \{[\s\S]*?\.overview-bottom-overlays \{[\s\S]*?right: 22rem;/
    );
    expect(styles).toMatch(
      /@media \(max-width: 44rem\) \{[\s\S]*?\.overview-page \{[\s\S]*?overflow-y: auto;/
    );
    expect(styles).toMatch(
      /@media \(max-width: 44rem\) \{[\s\S]*?\.globe-legend,[\s\S]*?\.overview-bottom-overlays \{[\s\S]*?position: relative;[\s\S]*?width: auto;/
    );
    expect(styles).toMatch(
      /\.overview-bottom-overlays \{[\s\S]*?pointer-events: none;/
    );
  });

  it('places the fullscreen control in reserved normal flow beside narrow POI states', () => {
    expect(styles).toMatch(
      /@media \(max-width: 44rem\) \{[\s\S]*?\.overview-fullscreen-control \{[\s\S]*?position: relative;[\s\S]*?bottom: auto;[\s\S]*?left: auto;[\s\S]*?margin: 1rem;/
    );
    expect(styles).toMatch(
      /@media \(max-width: 44rem\) \{[\s\S]*?\.overview-bottom-overlays \{[\s\S]*?position: relative;/
    );
  });
});
