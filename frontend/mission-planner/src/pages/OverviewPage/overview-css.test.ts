// @ts-expect-error Vitest runs this CSS contract in Node.
import { readFileSync } from 'node:fs';
// @ts-expect-error Vitest runs this CSS contract in Node.
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

declare const process: { cwd(): string };

const css = readFileSync(join(process.cwd(), 'src/index.css'), 'utf8');

describe('overview responsive CSS contract', () => {
  it('defines named overview classes and focus/reduced-motion rules', () => {
    for (const selector of [
      '.skip-link',
      '.overview-page',
      '.overview-grid',
      '.overview-map-region',
      '.overview-summary-strip',
      '.overview-fullscreen-button',
      '.overview-page--kiosk',
      '.overview-kiosk-active',
      ':focus-visible',
      '@media (prefers-reduced-motion: reduce)',
    ]) {
      expect(css).toContain(selector);
    }
    expect(css).not.toMatch(/body\s*{[^}]*overflow-x\s*:\s*hidden/s);
  });

  it('keeps navigation and controls at the 44px touch target floor', () => {
    expect(css).toMatch(/\.skip-link\s*{[^}]*min-height:\s*44px/s);
    expect(css).toMatch(/\.overview-fullscreen-button\s*{[^}]*min-height:\s*44px/s);
    expect(css).toMatch(/\.overview-fullscreen-button\s*{[^}]*min-width:\s*44px/s);
  });

  it('owns exact non-overlapping composed map heights', () => {
    expect(css).toMatch(/max-width:\s*320px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*280px/);
    expect(css).toMatch(/min-width:\s*321px\)[\s\S]*max-width:\s*767px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*320px/);
    expect(css).toMatch(/min-width:\s*768px\)[\s\S]*max-width:\s*1023px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*384px/);
    expect(css).toMatch(/min-width:\s*1024px\)[\s\S]*max-width:\s*1279px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*320px/);
    expect(css).toMatch(/min-width:\s*1280px\)[\s\S]*max-width:\s*1535px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*368px/);
    expect(css).toMatch(/min-width:\s*1536px\)[\s\S]*\.overview-map-region\s*{[^}]*height:\s*660px/);
  });
});
