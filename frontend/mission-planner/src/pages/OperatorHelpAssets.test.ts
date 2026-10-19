/** @vitest-environment jsdom */
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, resolve } from 'node:path';
import { expect, it } from 'vitest';
import { trainingSteps } from '@/components/operator/training/trainingSteps';
const root = resolve('public/operator-help');
const read = (name: string) => readFileSync(join(root, name), 'utf8');
const parse = (name: string) =>
  new DOMParser().parseFromString(read(name), 'text/html');
it('packages every curriculum guide section and resolves local links without an external service', () => {
  const guide = parse('guide.html');
  for (const step of trainingSteps)
    expect(guide.getElementById(step.guide), step.id).not.toBeNull();
  for (const name of ['guide.html', 'quick-reference.html']) {
    const doc = parse(name);
    expect(doc.documentElement.lang).toBe('en');
    expect(doc.querySelector('script,link[rel="stylesheet"]')).toBeNull();
    for (const anchor of doc.querySelectorAll('a[href]')) {
      const href = anchor.getAttribute('href')!;
      expect(href).not.toMatch(/^(https?:|\/\/|javascript:)/);
      if (href.startsWith('/operator')) continue;
      const [file, id] = href.split('#');
      const destination = file ? parse(file) : doc;
      if (id) expect(destination.getElementById(id), href).not.toBeNull();
    }
  }
});
it('packages unchanged synthetic screenshots with capture identity and readable descriptions', () => {
  const manifest = JSON.parse(read('images/provenance.json'));
  expect(manifest.synthetic).toBe(true);
  expect(manifest.candidateSha).toMatch(/^[a-f0-9]{40}$/);
  const guide = parse('guide.html');
  expect(guide.querySelectorAll('figure')).toHaveLength(3);
  for (const image of guide.querySelectorAll('img')) {
    expect(image.getAttribute('alt')!.length).toBeGreaterThan(40);
    expect(existsSync(join(root, image.getAttribute('src')!))).toBe(true);
  }
  for (const image of manifest.files) {
    const bytes = readFileSync(join(root, `images/${image.file}`));
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(image.sha256);
  }
});

it('resolves every parity matrix guide reference to the packaged manual', () => {
  const matrix = JSON.parse(readFileSync(resolve('../../tools/acceptance/operator-workspace/parity.json'), 'utf8'));
  const guide = parse('guide.html');
  expect(matrix.entries).toHaveLength(323);
  for (const entry of matrix.entries)
    expect(guide.getElementById(entry.guide_section), entry.id).not.toBeNull();
});
