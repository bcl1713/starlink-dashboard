import { test, expect } from '@playwright/test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

// Runs the same exact production journey; this spec never starts a dev server.
test('itinerary review, locks, conflicts, revisions and package round-trip', async () => {
  test.setTimeout(660_000);
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  expect(process.env.ITINERARY_ORIGIN).toBe('http://127.0.0.1:15322');
  const evidence = process.env.ITINERARY_EVIDENCE_DIR;
  expect(evidence).toBeTruthy();
  await promisify(execFile)(
    process.execPath,
    [resolve('../../tools/acceptance/browser/itinerary-planning.mjs')],
    {
      timeout: 600_000,
      env: process.env,
    }
  );
  const result = JSON.parse(
    await readFile(resolve(evidence!, 'browser-summary.json'), 'utf8')
  );
  expect(result.passed).toBe(true);
  expect(result.steps).toContain('package-collision-roundtrip');
  expect(result.steps).toContain('no-activation-or-terminal-side-effects');
});
