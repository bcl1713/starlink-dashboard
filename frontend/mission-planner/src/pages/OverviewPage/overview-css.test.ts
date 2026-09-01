import postcss, { type AtRule, type Rule } from 'postcss';
import { describe, expect, it } from 'vitest';

import { readSourceFile } from '../../test/read-source-file';

const indexCss = readSourceFile('src/index.css');
const overviewCss = readSourceFile('src/pages/OverviewPage/overview.css');
const sourceCss = `${indexCss}\n${overviewCss}`;

interface DeclarationRecord {
  readonly selector: string;
  readonly prop: string;
  readonly value: string;
  readonly important: boolean;
  readonly media: string | null;
  readonly order: number;
}

interface ElementTarget {
  readonly classes?: readonly string[];
  readonly pseudos?: readonly string[];
  readonly ancestors?: readonly ElementTarget[];
}

type Specificity = readonly [number, number, number];

function declarations(css = sourceCss): DeclarationRecord[] {
  const output: DeclarationRecord[] = [];
  let order = 0;
  postcss.parse(css).walkRules((rule: Rule) => {
    rule.walkDecls((decl) => {
      for (const selector of rule.selector.split(',')) {
        output.push({
          selector: selector.trim(),
          prop: decl.prop,
          value: decl.value,
          important: decl.important,
          media: parentMedia(rule),
          order,
        });
      }
      order += 1;
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
  target: ElementTarget,
  prop: string,
  width: number,
  css = sourceCss
): string | null {
  let winner: (DeclarationRecord & { specificity: Specificity }) | null = null;
  for (const declaration of declarations(css)) {
    if (
      declaration.prop !== prop ||
      !mediaMatches(declaration.media, width) ||
      !selectorMatches(declaration.selector, target)
    ) {
      continue;
    }
    const specificity = selectorSpecificity(declaration.selector);
    const candidate = { ...declaration, specificity };
    if (!winner || compareCascade(candidate, winner) > 0) winner = candidate;
  }
  if (!winner) return null;
  return winner.important ? `${winner.value} !important` : winner.value;
}

function selectorMatches(selector: string, target: ElementTarget): boolean {
  const parts = selector.trim().split(/\s+/);
  let cursor: ElementTarget | undefined = target;
  for (let index = parts.length - 1; index >= 0; index -= 1) {
    if (!cursor) return false;
    const part = parts[index];
    if (compoundMatches(part, cursor)) {
      cursor = cursor.ancestors?.[0];
      continue;
    }
    let ancestor = cursor.ancestors?.[0];
    while (ancestor && !compoundMatches(part, ancestor)) {
      ancestor = ancestor.ancestors?.[0];
    }
    if (!ancestor) return false;
    cursor = ancestor.ancestors?.[0];
  }
  return true;
}

function compoundMatches(compound: string, target: ElementTarget): boolean {
  if (compound === '*') return true;
  for (const name of compound.match(/\.[\w-]+/g) ?? []) {
    if (!target.classes?.includes(name.slice(1))) return false;
  }
  for (const name of compound.match(/:[\w-]+/g) ?? []) {
    if (!target.pseudos?.includes(name.slice(1))) return false;
  }
  return !/^[a-z]/i.test(compound);
}

function selectorSpecificity(selector: string): Specificity {
  const ids = selector.match(/#[\w-]+/g)?.length ?? 0;
  const classes = selector.match(/[.:][\w-]+|\[[^\]]+\]/g)?.length ?? 0;
  const elements = selector
    .split(/\s+/)
    .filter((part) => /^[a-z]/i.test(part)).length;
  return [ids, classes, elements];
}

function compareCascade(
  candidate: DeclarationRecord & { specificity: Specificity },
  current: DeclarationRecord & { specificity: Specificity }
): number {
  if (candidate.important !== current.important) {
    return candidate.important ? 1 : -1;
  }
  for (let index = 0; index < 3; index += 1) {
    const diff = candidate.specificity[index] - current.specificity[index];
    if (diff !== 0) return diff;
  }
  return candidate.order - current.order;
}

const mapRegion: ElementTarget = {
  classes: ['overview-map-region'],
  ancestors: [{ classes: ['overview-page'] }],
};

describe('overview responsive CSS contract', () => {
  it('keeps index.css below the cohesion line guard', () => {
    expect(indexCss.split('\n').length).toBeLessThanOrEqual(300);
  });

  it('computes effective map region heights at exact accepted widths', () => {
    expect(
      [320, 390, 768, 1024, 1280, 1920].map((width) => [
        width,
        effective(mapRegion, 'height', width),
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
        effective(
          { classes: ['overview-primary-grid'] },
          'grid-template-rows',
          width
        )
      ).toBe('auto auto');
      expect(
        effective({ classes: ['overview-right-rail'] }, 'grid-column', width)
      ).toBe('2');
      expect(
        effective({ classes: ['overview-right-rail'] }, 'grid-row', width)
      ).toBe('1 / 3');
    }
    expect(
      effective({ classes: ['overview-page--kiosk'] }, 'position', 390)
    ).toBe('fixed');
    expect(
      effective({ classes: ['overview-page--kiosk'] }, 'height', 390)
    ).toBe('100dvh');
    expect(
      effective(
        { classes: ['overview-page'], pseudos: ['fullscreen'] },
        'height',
        1280
      )
    ).toBe('100dvh');
    expect(effective({ pseudos: ['focus-visible'] }, 'outline', 390)).toBe(
      '3px solid var(--ring)'
    );
  });

  it('detects applicable specificity and important overrides in fixtures', () => {
    const fixture = `
      .overview-map-region, .unused { height: 1px; }
      .overview-page .overview-map-region { height: 2px; }
      .later { height: 3px; }
      .overview-map-region { height: 4px !important; }
    `;
    expect(effective(mapRegion, 'height', 390, fixture)).toBe('4px !important');
    expect(
      effective(mapRegion, 'height', 390, fixture.replace(' !important', ''))
    ).toBe('2px');
  });

  it('keeps reduced motion declarations in the parsed media rules', () => {
    const reduced = declarations().filter(
      (item) => item.media === '(prefers-reduced-motion: reduce)'
    );
    expect(
      reduced.map((item) => [
        item.prop,
        item.important ? `${item.value} !important` : item.value,
      ])
    ).toEqual(
      expect.arrayContaining([
        ['scroll-behavior', 'auto !important'],
        ['animation-duration', '0.01ms !important'],
        ['animation-iteration-count', '1 !important'],
        ['transition-duration', '0.01ms !important'],
      ])
    );
  });
});
