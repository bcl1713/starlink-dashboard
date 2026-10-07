import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { renderStage } from '../../src/mission-export/render.mjs';
import { readFileSync } from 'node:fs';
const fixture = JSON.parse(
  readFileSync(
    new URL(
      '../../../../backend/starlink-location/tests/fixtures/customer_briefing/f08_map_inputs.json',
      import.meta.url
    ),
    'utf8'
  )
);

// Real packaged/built scene. Breaks caught: premature readiness, blanks,
// nondeterministic pixels, missing views, leaked listener/browser on errors.
test('renders every primary view offline, with deterministic geometry and decoded pixels', async () => {
  const output = await mkdtemp(path.join(tmpdir(), 'mission-map-pixels-'));
  try {
    const marked = {
      ...fixture.legs[0],
      markers: [
        { id: 'synthetic-start', label: '1', routeIndex: 0 },
        { id: 'synthetic-end', label: '2', routeIndex: 1 },
      ],
    };
    const result = await renderStage({
      legs: [marked, marked],
      output,
      assetRoot: path.resolve('dist-mission-export'),
      budgetSeconds: 60,
    });
    if (process.env.MISSION_MAP_BROWSER_EVIDENCE) {
      await mkdir(process.env.MISSION_MAP_BROWSER_EVIDENCE, {
        recursive: true,
      });
      for (const [i, view] of result.views.entries())
        await writeFile(
          path.join(
            process.env.MISSION_MAP_BROWSER_EVIDENCE,
            `identical-${i}.png`
          ),
          await readFile(view.path)
        );
      await writeFile(
        path.join(process.env.MISSION_MAP_BROWSER_EVIDENCE, 'identical.json'),
        JSON.stringify(result, null, 2)
      );
    }
    expect(result.status).toBe('primary');
    expect(result.views).toHaveLength(2);
    expect(result.views[0].readiness.framing).toEqual(
      result.views[1].readiness.framing
    );
    expect(result.views[0].pixelHash).toBe(result.views[1].pixelHash);
    expect(result.views[0].pngHash).toBe(result.views[1].pngHash);
    expect(result.views[0].readiness.stages).toEqual([
      'textures-decoded',
      'shaders-compiled',
      'camera-settled',
      'labels-projected',
      'render-complete',
    ]);
    expect(result.views[0].width).toBe(1920);
    expect(result.views[0].height).toBe(1080);
    expect(
      createHash('sha256')
        .update(await readFile(result.views[0].path))
        .digest('hex')
    ).toBe(result.views[0].pngHash);
    expect(result.cleanup).toMatchObject({
      listenerClosed: true,
      browserExited: true,
      contextsClosed: true,
    });
  } finally {
    await rm(output, { recursive: true, force: true });
  }
});
for (const fault of ['startup', 'texture', 'context-loss', 'slow'] as const) {
  test(`reports labeled fallback and cleans up after ${fault}`, async () => {
    const output = await mkdtemp(path.join(tmpdir(), `mission-map-${fault}-`));
    try {
      const result = await renderStage({
        legs: fixture.legs,
        output,
        assetRoot: path.resolve('dist-mission-export'),
        budgetSeconds: fault === 'slow' ? 2 : 15,
        fault,
      });
      if (process.env.MISSION_MAP_BROWSER_EVIDENCE) {
        await mkdir(process.env.MISSION_MAP_BROWSER_EVIDENCE, {
          recursive: true,
        });
        await writeFile(
          path.join(process.env.MISSION_MAP_BROWSER_EVIDENCE, `${fault}.json`),
          JSON.stringify(result, null, 2)
        );
      }
      expect(result.status).toBe('fallback');
      expect(result.fallbackLabel).toBe(
        'Overview map unavailable — static route fallback'
      );
      expect(result.error).toMatch(
        fault === 'slow'
          ? /deadline/i
          : fault === 'startup'
            ? /executable|launch|browser/i
            : fault === 'texture'
              ? /texture|load/i
              : /context/i
      );
      expect(result.views).toHaveLength(0);
      expect(result.cleanup).toMatchObject({
        listenerClosed: true,
        browserExited: true,
        contextsClosed: true,
      });
      expect(result.elapsedSeconds).toBeLessThan(fault === 'slow' ? 4 : 15);
    } finally {
      await rm(output, { recursive: true, force: true });
    }
  });
}
