// @ts-expect-error Vitest runs this CSS contract in Node.
import { readFileSync } from 'node:fs';
// @ts-expect-error Vitest runs this CSS contract in Node.
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

declare const process: { cwd(): string };

const root = process.cwd();
const indexCss = readFileSync(join(root, 'src/index.css'), 'utf8');
const overviewCss = readFileSync(
  join(root, 'src/pages/OverviewPage/overview.css'),
  'utf8'
);

function selectorBlock(css: string, selector: string): string {
  const start = css.indexOf(`${selector} {`);
  expect(start).toBeGreaterThanOrEqual(0);
  const bodyStart = css.indexOf('{', start) + 1;
  const end = css.indexOf('}', bodyStart);
  return css.slice(bodyStart, end);
}

function mediaBlock(query: string): string {
  const start = overviewCss.indexOf(`@media ${query} {`);
  expect(start).toBeGreaterThanOrEqual(0);
  const bodyStart = overviewCss.indexOf('{', start);
  let depth = 0;
  for (let index = bodyStart; index < overviewCss.length; index += 1) {
    if (overviewCss[index] === '{') depth += 1;
    if (overviewCss[index] === '}') depth -= 1;
    if (depth === 0 && index > start) return overviewCss.slice(start, index);
  }
  throw new Error(`Unclosed media block: ${query}`);
}

function declaration(block: string, name: string): string | null {
  const match = new RegExp(`${name}:\\s*([^;]+);`).exec(block);
  return match?.[1].trim() ?? null;
}

describe('overview responsive CSS contract', () => {
  it('keeps index.css below the cohesion line guard', () => {
    expect(indexCss.split('\n').length).toBeLessThanOrEqual(300);
  });

  it('defines exact fullscreen, kiosk, focus, and reduced-motion rules', () => {
    expect(selectorBlock(indexCss, ':focus-visible')).toContain(
      'outline: 3px solid var(--ring);'
    );
    const kiosk = selectorBlock(overviewCss, '.overview-page--kiosk');
    expect(declaration(kiosk, 'position')).toBe('fixed');
    expect(declaration(kiosk, 'inset')).toBe('0');
    expect(declaration(kiosk, 'height')).toBe('100dvh');
    expect(declaration(kiosk, 'overflow-y')).toBe('auto');
    expect(declaration(kiosk, 'overflow-x')).toBe('clip');
    const native = selectorBlock(overviewCss, '.overview-page:fullscreen');
    expect(declaration(native, 'width')).toBe('100vw');
    expect(declaration(native, 'height')).toBe('100dvh');
    const reduced = mediaBlock('(prefers-reduced-motion: reduce)');
    expect(reduced).toContain('scroll-behavior: auto !important;');
    expect(reduced).toContain('animation-duration: 0.01ms !important;');
    expect(reduced).toContain('animation-iteration-count: 1 !important;');
    expect(reduced).toContain('transition-duration: 0.01ms !important;');
  });

  it('places desktop and wide composition without an implicit third root row', () => {
    for (const query of [
      '(min-width: 1024px) and (max-width: 1279px)',
      '(min-width: 1280px) and (max-width: 1535px)',
      '(min-width: 1536px)',
    ]) {
      const media = mediaBlock(query);
      const grid = selectorBlock(media, '.overview-primary-grid');
      const rail = selectorBlock(media, '.overview-right-rail');
      expect(declaration(grid, 'grid-template-columns')).toContain('minmax');
      expect(declaration(grid, 'grid-template-rows')).toBe('auto auto');
      expect(declaration(rail, 'grid-column')).toBe('2');
      expect(declaration(rail, 'grid-row')).toBe('1 / 3');
    }
  });

  it('computes exact map heights at all accepted widths', () => {
    const cases = [
      ['(max-width: 320px)', '280px'],
      ['(min-width: 321px) and (max-width: 767px)', '320px'],
      ['(min-width: 768px) and (max-width: 1023px)', '384px'],
      ['(min-width: 1024px) and (max-width: 1279px)', '320px'],
      ['(min-width: 1280px) and (max-width: 1535px)', '368px'],
      ['(min-width: 1536px)', '660px'],
    ] as const;
    for (const [query, height] of cases) {
      const block = selectorBlock(mediaBlock(query), '.overview-map-region');
      expect(declaration(block, 'height')).toBe(height);
    }
  });
});
