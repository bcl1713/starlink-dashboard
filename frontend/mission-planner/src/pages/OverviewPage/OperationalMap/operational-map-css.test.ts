import { describe, expect, it } from 'vitest';

describe('operational map CSS', () => {
  it('lets the composed map region own height without local clamps', async () => {
    // @ts-expect-error Vitest runs this local file read in Node.
    const { readFileSync } = await import('node:fs');
    const cwd = (
      globalThis as unknown as { process: { cwd(): string } }
    ).process.cwd();
    const css = readFileSync(
      `${cwd}/src/pages/OverviewPage/OperationalMap/operational-map.css`,
      'utf8'
    );

    expect(css).not.toContain('min-height: 320px');
    expect(css).not.toContain('vh');
    expect(css).toContain('height: 100%');
    expect(css).toContain('min-height: 0');
  });

  it('assigns explicit 44px targets to feature, dismiss, and summary controls', async () => {
    // @ts-expect-error Vitest runs this local file read in Node.
    const { readFileSync } = await import('node:fs');
    const cwd = (
      globalThis as unknown as { process: { cwd(): string } }
    ).process.cwd();
    const css = readFileSync(
      `${cwd}/src/pages/OverviewPage/OperationalMap/operational-map.css`,
      'utf8'
    );

    for (const className of [
      'operational-map__feature-button',
      'operational-map__details-dismiss',
      'operational-map__layer-summary',
    ]) {
      expect(css).toContain(`.${className}`);
    }
    expect(css).toMatch(/min-height:\s*44px/);
    expect(css).toMatch(/min-width:\s*44px/);
  });
});
