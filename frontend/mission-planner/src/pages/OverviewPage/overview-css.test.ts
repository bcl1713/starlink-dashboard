// @ts-expect-error Vitest runs this CSS contract in Node.
import { readFileSync } from 'node:fs';
// @ts-expect-error Vitest runs this CSS contract in Node.
import { join } from 'node:path';
import postcss, { type AtRule, type Rule } from 'postcss';
import { describe, expect, it } from 'vitest';

declare const process: { cwd(): string };

const root = process.cwd();
const indexCss = readFileSync(join(root, 'src/index.css'), 'utf8');
const overviewCss = readFileSync(
  join(root, 'src/pages/OverviewPage/overview.css'),
  'utf8'
);
const stylesheet = postcss.parse(`${indexCss}\n${overviewCss}`);

interface DeclarationRecord {
  readonly selector: string;
  readonly prop: string;
  readonly value: string;
  readonly media: string | null;
}

function declarations(): DeclarationRecord[] {
  const output: DeclarationRecord[] = [];
  stylesheet.walkRules((rule: Rule) => {
    rule.walkDecls((decl) => {
      output.push({
        selector: rule.selector,
        prop: decl.prop,
        value: decl.important ? `${decl.value} !important` : decl.value,
        media: parentMedia(rule),
      });
    });
  });
  return output;
}

function parentMedia(rule: Rule): string | null {
  let parent: { type: string; parent?: unknown } | undefined = rule.parent as
    | { type: string; parent?: unknown }
    | undefined;
  while (parent) {
    if (parent.type === 'atrule' && (parent as AtRule).name === 'media') {
      return (parent as AtRule).params;
    }
    parent = parent.parent as typeof parent;
  }
  return null;
}

function mediaMatches(media: string | null, width: number): boolean {
  if (!media) return true;
  const min = /min-width:\s*(\d+)px/.exec(media)?.[1];
  const max = /max-width:\s*(\d+)px/.exec(media)?.[1];
  if (min && width < Number(min)) return false;
  if (max && width > Number(max)) return false;
  return !media.includes('prefers-reduced-motion');
}

function effective(
  selector: string,
  prop: string,
  width: number
): string | null {
  let value: string | null = null;
  for (const declaration of declarations()) {
    if (
      declaration.selector === selector &&
      declaration.prop === prop &&
      mediaMatches(declaration.media, width)
    ) {
      value = declaration.value;
    }
  }
  return value;
}

describe('overview responsive CSS contract', () => {
  it('keeps index.css below the cohesion line guard', () => {
    expect(indexCss.split('\n').length).toBeLessThanOrEqual(300);
  });

  it('computes effective map region heights at exact accepted widths', () => {
    expect(
      [320, 390, 768, 1024, 1280, 1920].map((width) => [
        width,
        effective('.overview-map-region', 'height', width),
      ])
    ).toEqual([
      [320, '280px'],
      [390, '320px'],
      [768, '384px'],
      [1024, '320px'],
      [1280, '368px'],
      [1920, '660px'],
    ]);
  });

  it('computes right rail placement and fullscreen essentials by cascade', () => {
    for (const width of [1024, 1280, 1920]) {
      expect(
        effective('.overview-primary-grid', 'grid-template-rows', width)
      ).toBe('auto auto');
      expect(effective('.overview-right-rail', 'grid-column', width)).toBe('2');
      expect(effective('.overview-right-rail', 'grid-row', width)).toBe(
        '1 / 3'
      );
    }
    expect(effective('.overview-page--kiosk', 'position', 390)).toBe('fixed');
    expect(effective('.overview-page--kiosk', 'height', 390)).toBe('100dvh');
    expect(effective('.overview-page:fullscreen', 'height', 1280)).toBe(
      '100dvh'
    );
    expect(effective(':focus-visible', 'outline', 390)).toBe(
      '3px solid var(--ring)'
    );
  });

  it('keeps reduced motion declarations in the parsed media rules', () => {
    const reduced = declarations().filter(
      (item) => item.media === '(prefers-reduced-motion: reduce)'
    );
    expect(reduced.map((item) => [item.prop, item.value])).toEqual(
      expect.arrayContaining([
        ['scroll-behavior', 'auto !important'],
        ['animation-duration', '0.01ms !important'],
        ['animation-iteration-count', '1 !important'],
        ['transition-duration', '0.01ms !important'],
      ])
    );
  });
});
